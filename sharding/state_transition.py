from ethereum.common import mk_transaction_sha, mk_receipt_sha
from ethereum.messages import apply_transaction
from ethereum.exceptions import InsufficientBalance, BlockGasLimitReached, \
    InsufficientStartGas, InvalidNonce, UnsignedTransaction
from ethereum.slogging import get_logger

from sharding.collation import Collation, CollationHeader

log = get_logger('sharding.shard_state_transition')


def mk_collation_from_prevstate(chain, state=None, timestamp=None, coinbase='\x35' * 20):
    """Make collation from previous state (refer to mk_blk_from_prevstate)
    """
    state = state or chain.shard_state
    collation = Collation(CollationHeader(), [])
    collation.header.shardId = chain.shardId
    collation.header.prev_state_root = state.trie.root_hash
    collation.header.coinbase = coinbase
    return collation


def add_transactions(state, collation, txqueue, min_gasprice=0):
    """Add transactions to a collation
    """
    if not txqueue:
        return
    pre_txs = len(collation.transactions)
    log.info('Adding transactions, %d in txqueue, %d dunkles' % (len(txqueue.txs), pre_txs))
    while 1:
        tx = txqueue.pop_transaction(max_gas=state.gas_limit - state.gas_used,
                                     min_gasprice=min_gasprice)
        if tx is None:
            break
        try:
            apply_transaction(state, tx)
            collation.transactions.append(tx)
        except (InsufficientBalance, BlockGasLimitReached, InsufficientStartGas,
                InvalidNonce, UnsignedTransaction) as e:
            print(str(e))
            pass
    log.info('Added %d transactions' % (len(collation.transactions) - pre_txs))


def update_collation_env_variables(state, collation):
    """Update collation variables into the state (refer to update_blk_env_variables)
    """
    state.block_coinbase = collation.header.coinbase


def initialize(state, collation=None):
    """Collation initialization state transition (refer to ethereum.pow.consensus.initialize)
    """
    state.txindex = 0
    state.gas_used = 0
    state.bloom = 0
    state.receipts = []

    # TODO: set to what?
    # state.timestamp
    # state.gas_limit
    # state.block_number = collation.header.number
    # state.recent_uncles[state.block_number] = [x.hash for x in block.uncles]
    # state.block_difficulty = collation.header.difficulty

    if collation is not None:
        update_collation_env_variables(state, collation)

    if state.is_DAO(at_fork_height=True):
        for acct in state.config['CHILD_DAO_LIST']:
            state.transfer_value(acct, state.config['DAO_WITHDRAWER'], state.get_balance(acct))

    # config = state.config
    # if state.is_METROPOLIS(at_fork_height=True):
    #     state.set_code(utils.normalize_address(
    #         config["METROPOLIS_STATEROOT_STORE"]), config["METROPOLIS_GETTER_CODE"])
    #     state.set_code(utils.normalize_address(
    #         config["METROPOLIS_BLOCKHASH_STORE"]), config["METROPOLIS_GETTER_CODE"])


def set_execution_results(state, collation):
    """Set state root, receipt root, etc (ethereum.pow.common.set_execution_results)
    """
    collation.header.receipts_root = mk_receipt_sha(state.receipts)
    collation.header.tx_list_root = mk_transaction_sha(collation.transactions)
    state.commit()
    collation.header.post_state_root = state.trie.root_hash

    # TODO: Don't handle in basic sharding currently
    # block.header.gas_used = state.gas_used
    # block.header.bloom = state.bloom

    log.info('Collation pre-sealed, %d gas used' % state.gas_used)
