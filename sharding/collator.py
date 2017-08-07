from ethereum.slogging import get_logger
from ethereum.consensus_strategy import get_consensus_strategy
from ethereum.messages import apply_transaction
from ethereum import utils

from sharding import state_transition

log = get_logger('sharding.collator')


def apply_collation(state, collation, period_start_prevblock):
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
            apply_transaction(state, tx)
        # Set state root, receipt root, etc
        state_transition.finalize(state, collation.header.coinbase)
        assert state_transition.verify_execution_results(state, collation)
    except (ValueError, AssertionError) as e:
        state.revert(snapshot)
        raise e
    return state


def create_collation(
        chain,
        shardId,
        parent_collation_hash,
        expected_period_number,
        coinbase,
        key,
        txqueue=None):
    """Create a collation

    chain: MainChain
    shardId: id of ShardChain
    parent_collation_hash: the hash of the parent collation
    expected_period_number: the period number in which this collation expects to be included
    coinbase: coinbase
    key: key for sig
    txqueue: transaction queue
    """
    log.info('Creating a collation')

    assert chain.has_shard(shardId)

    temp_state = chain.shards[shardId].mk_poststate_of_collation_hash(parent_collation_hash)
    cs = get_consensus_strategy(temp_state.config)

    # Set period_start_prevblock info
    period_start_prevhash = chain.get_period_start_prevhash(expected_period_number)
    assert period_start_prevhash is not None
    period_start_prevblock = chain.get_block(period_start_prevhash)
    # Call the initialize state transition function
    cs.initialize(temp_state, period_start_prevblock)
    # Initialize a collation with the given previous state and current coinbase
    collation = state_transition.mk_collation_from_prevstate(chain.shards[shardId], temp_state, coinbase)
    # Add transactions
    state_transition.add_transactions(temp_state, collation, txqueue)
    # Call the finalize state transition function
    state_transition.finalize(temp_state, collation.header.coinbase)
    # Set state root, receipt root, etc
    state_transition.set_execution_results(temp_state, collation)

    collation.header.shardId = shardId
    collation.header.parent_collation_hash = parent_collation_hash
    collation.header.expected_period_number = expected_period_number
    collation.header.period_start_prevhash = period_start_prevhash

    try:
        sig = sign(collation.signing_hash, key)
        collation.header.sig = sig
    except Exception as e:
        log.info('Failed to sign collation, exception: {}'.format(str(e)))

    log.info('Created collation successfully')
    return collation


def sign(msg_hash, privkey):
    """Use privkey to ecdsa-sign the msg_hash
    """
    v, r, s = utils.ecsign(msg_hash, privkey)
    signature = utils.encode_int32(v) + utils.encode_int32(r) + utils.encode_int32(s)
    return signature
