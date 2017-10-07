import rlp

from ethereum.slogging import get_logger
from ethereum.consensus_strategy import get_consensus_strategy
from ethereum.common import mk_block_from_prevstate
from ethereum.state import State
from ethereum.exceptions import VerificationFailed

from sharding import state_transition
from sharding.contract_utils import sign
from sharding.validator_manager_utils import call_valmgr
from sharding.receipt_consuming_tx_utils import apply_shard_transaction

log = get_logger('sharding.collator')


def apply_collation(state, collation, period_start_prevblock, mainchain_state, shard_id=None):
    """Apply collation
    """
    snapshot = state.snapshot()
    cs = get_consensus_strategy(state.config)

    try:
        # Call the initialize state transition function
        cs.initialize(state, period_start_prevblock)
        # Collation Gas Limit
        gas_limit = call_valmgr(mainchain_state, 'get_collation_gas_limit', [])
        state_transition.set_collation_gas_limit(state, gas_limit)
        # assert cs.check_seal(state, period_start_prevblock.header)
        # Validate tx_list_root in collation first
        assert state_transition.validate_transaction_tree(collation)
        for tx in collation.transactions:
            apply_shard_transaction(
                mainchain_state, state, shard_id, tx
            )
        # Set state root, receipt root, etc
        state_transition.finalize(state, collation.header.coinbase)
        assert state_transition.verify_execution_results(state, collation)
    except (ValueError, AssertionError) as e:
        state.revert(snapshot)
        raise e
    return state


def create_collation(
        chain,
        shard_id,
        parent_collation_hash,
        expected_period_number,
        coinbase,
        key,
        txqueue=None,
        period_start_prevhash=None):
    """Create a collation

    chain: MainChain
    shard_id: id of ShardChain
    parent_collation_hash: the hash of the parent collation
    expected_period_number: the period number in which this collation expects to be included
    coinbase: coinbase
    key: key for sig
    txqueue: transaction queue
    period_start_prevhash: the block hash of block PERIOD_LENGTH * expected_period_number - 1
    """
    log.info('Creating a collation')

    assert chain.has_shard(shard_id)

    temp_state = chain.shards[shard_id].mk_poststate_of_collation_hash(parent_collation_hash)
    cs = get_consensus_strategy(temp_state.config)

    # Set period_start_prevblock info
    if period_start_prevhash is None:
        period_start_prevhash = chain.get_period_start_prevhash(expected_period_number)
        assert period_start_prevhash is not None
    period_start_prevblock = chain.get_block(period_start_prevhash)
    # Call the initialize state transition function
    cs.initialize(temp_state, period_start_prevblock)
    # Collation Gas Limit
    gas_limit = call_valmgr(chain.state, 'get_collation_gas_limit', [])
    state_transition.set_collation_gas_limit(temp_state, gas_limit)
    # Initialize a collation with the given previous state and current coinbase
    collation = state_transition.mk_collation_from_prevstate(chain.shards[shard_id], temp_state, coinbase)
    # Add transactions
    state_transition.add_transactions(temp_state, collation, txqueue, chain.state, shard_id)
    # Call the finalize state transition function
    state_transition.finalize(temp_state, collation.header.coinbase)
    # Set state root, receipt root, etc
    state_transition.set_execution_results(temp_state, collation)

    collation.header.shard_id = shard_id
    collation.header.parent_collation_hash = parent_collation_hash
    collation.header.expected_period_number = expected_period_number
    collation.header.period_start_prevhash = period_start_prevhash
    collation.header.number = chain.shards[shard_id].get_collation(parent_collation_hash).number + 1

    try:
        sig = sign(collation.signing_hash, key)
        collation.header.sig = sig
    except Exception as e:
        log.info('Failed to sign collation, exception: {}'.format(str(e)))
        raise e

    log.info('Created collation successfully')
    return collation


def verify_collation_header(chain, header):
    """Verify the collation

    Validate the collation header before calling ShardChain.add_collation

    chain: MainChain
    header: the given collation header
    """
    if header.shard_id < 0:
        raise ValueError('Invalid shard_id %d' % header.shard_id)

    # Call contract to verify header
    state = chain.state.ephemeral_clone()
    block = mk_block_from_prevstate(chain, timestamp=chain.state.timestamp + 14)
    cs = get_consensus_strategy(state.config)
    cs.initialize(state, block)
    # Collation Gas Limit
    gas_limit = call_valmgr(chain.state, 'get_collation_gas_limit', [])
    state_transition.set_collation_gas_limit(state, gas_limit)
    try:
        result = call_valmgr(
            state, 'add_header',
            [rlp.encode(header)],
            sender_addr=header.coinbase
        )
        if not result:
            raise ValueError('Calling add_header returns False')
    except Exception as e:
        raise ValueError('Failed to call add_header', str(e))
    return True


def get_deep_collation_hash(chain, shard_id, depth):
    """ Get the deep collation hash from validator manager contract

    chain: MainChain
    shard_id: id of ShardChain
    depth: the depth between the head collation to the ancestor collation
    """
    collhash = call_valmgr(chain.state, 'get_shard_head', [shard_id])

    for _ in range(depth):
        temp_collhash = call_valmgr(
            chain.state,
            'get_collation_headers__parent_collation_hash',
            [shard_id, collhash]
        )
        if temp_collhash == b'\x00' * 32:
            break
        else:
            collhash = temp_collhash

    return collhash


def mk_fast_sync_state(chain, shard_id, collation_hash):
    """ Make the fast sync state

    chain: MainChain
    shard_id: id of ShardChain
    collation_hash: the collation hash of the pivot point collation
    """
    collation = chain.shards[shard_id].get_collation(collation_hash)

    if collation is not None:
        state_root = collation.post_state_root
        state = State(env=chain.shards[shard_id].env, root=state_root)
        return state
    else:
        return None


def verify_fast_sync_data(chain, shard_id, received_state, received_collation_header, depth=100):
    """ Verify the fast sync data

    chain: MainChain
    received_state: the given shard state from peer
    received_collation_header: the given collation header
    depth: the required depth between the given collation and the head collation on validator manager contract
    """
    # Check if the given collation exsits in validator manager contract
    received_collation_score = call_valmgr(
        chain.state,
        'get_collation_headers__score',
        [shard_id, received_collation_header.hash]
    )
    if received_collation_score <= 0:
        raise VerificationFailed('FastSync: received_collation_score {} <= 0'.format(received_collation_score))

    # Check if the state root is right
    if received_state.trie.root_hash != received_collation_header.post_state_root:
        raise VerificationFailed('FastSync: state roots don\'t match, received state: {}, received_collation_header.post_state_root: {}.'.format(
            received_state.trie.root_hash,
            received_collation_header.post_state_root
        ))

    # Check if the given collation is deep enough (likely finalized)
    head_collation_hash = call_valmgr(chain.state, 'get_shard_head', [shard_id])
    head_collation_score = call_valmgr(
        chain.state,
        'get_collation_headers__score',
        [shard_id, head_collation_hash]
    )
    if head_collation_score > received_collation_score + depth:
        raise VerificationFailed('FastSync: head_collation_score({}) > received_collation_score({}) + depth({})'.format(
            head_collation_score,
            received_collation_score,
            depth
        ))

    return True
