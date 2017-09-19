import rlp

from ethereum.slogging import get_logger
from ethereum.consensus_strategy import get_consensus_strategy
from ethereum.messages import apply_transaction
from ethereum.common import mk_block_from_prevstate
from ethereum.utils import big_endian_to_int

from sharding import state_transition
from sharding.validator_manager_utils import (sign, call_valmgr)
from sharding.collation import CollationHeader
from sharding.receipt_consuming_tx_utils import apply_shard_transaction

log = get_logger('sharding.collator')


def apply_collation(state, collation, period_start_prevblock, mainchain_state=None, shard_id=None):
    """Apply collation
    """
    snapshot = state.snapshot()
    cs = get_consensus_strategy(state.config)

    try:
        # Call the initialize state transition function
        cs.initialize(state, period_start_prevblock)
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
        txqueue=None):
    """Create a collation

    chain: MainChain
    shard_id: id of ShardChain
    parent_collation_hash: the hash of the parent collation
    expected_period_number: the period number in which this collation expects to be included
    coinbase: coinbase
    key: key for sig
    txqueue: transaction queue
    """
    log.info('Creating a collation')

    assert chain.has_shard(shard_id)

    temp_state = chain.shards[shard_id].mk_poststate_of_collation_hash(parent_collation_hash)
    cs = get_consensus_strategy(temp_state.config)

    # Set period_start_prevblock info
    period_start_prevhash = chain.get_period_start_prevhash(expected_period_number)
    assert period_start_prevhash is not None
    period_start_prevblock = chain.get_block(period_start_prevhash)
    # Call the initialize state transition function
    cs.initialize(temp_state, period_start_prevblock)
    # Initialize a collation with the given previous state and current coinbase
    collation = state_transition.mk_collation_from_prevstate(chain.shards[shard_id], temp_state, coinbase)
    # Add transactions
    state_transition.add_transactions(temp_state, collation, txqueue, shard_id, mainchain_state=chain.state)
    # Call the finalize state transition function
    state_transition.finalize(temp_state, collation.header.coinbase)
    # Set state root, receipt root, etc
    state_transition.set_execution_results(temp_state, collation)

    collation.header.shard_id = shard_id
    collation.header.parent_collation_hash = parent_collation_hash
    collation.header.expected_period_number = expected_period_number
    collation.header.period_start_prevhash = period_start_prevhash

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

    try:
        result = call_valmgr(
            state, 'add_header',
            [rlp.encode(header)],
            sender_addr=header.coinbase
        )
        print('result:{}'.format(result))
        if not result:
            raise ValueError('Calling add_header returns False')
    except:
        raise ValueError('Calling add_header failed')
    return True
