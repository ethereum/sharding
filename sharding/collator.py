import copy

from ethereum.utils import sha3, decode_hex, encode_hex
from ethereum.transaction_queue import TransactionQueue
from ethereum.slogging import get_logger
from ethereum.common import mk_receipt_sha, mk_transaction_sha

from sharding import contract_utils
from sharding import state_transition

log = get_logger('sharding.collator')

# TODO
def apply_collation(shard_chain, collation):
    return True

def create_collation(
        chain,
        prev_state,
        parent_collation_hash,
        txqueue=None,
        expected_period_number=0,
        coinbase='\x35' * 20
       ):
    """Create collation on top of the given chain
    """
    log.info('Creating a collation')

    # Apply state transition and generate collation
    temp_state = prev_state.ephemeral_clone()
    collation = state_transition.mk_collation_from_prevstate(chain, temp_state, coinbase)
    state_transition.initialize(temp_state, collation)
    state_transition.add_transactions(temp_state, collation, txqueue)
    state_transition.set_execution_results(temp_state, collation)
    # TODO finalize, incentives
    temp_state.commit()

    collation.header.shardId = chain.shardId
    collation.header.parent_collation_hash = parent_collation_hash
    collation.header.expected_period_number = expected_period_number

    log.info('Created collation successfully')
    return collation