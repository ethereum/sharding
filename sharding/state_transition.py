from ethereum.common import mk_transaction_sha, mk_receipt_sha
from ethereum.messages import apply_transaction
from ethereum.exceptions import InsufficientBalance, BlockGasLimitReached, \
    InsufficientStartGas, InvalidNonce, UnsignedTransaction
from ethereum.slogging import get_logger
from ethereum.utils import encode_hex

from sharding.collation import Collation, CollationHeader

log = get_logger('sharding.shard_state_transition')


def mk_collation_from_prevstate(shard_chain, state, coinbase):
    """Make collation from previous state (refer to mk_blk_from_prevstate)
    """
    # state = state or shard_chain.state
    collation = Collation(CollationHeader())
    collation.header.shardId = shard_chain.shardId
    collation.header.prev_state_root = state.trie.root_hash
    collation.header.coinbase = coinbase
    collation.transactions = []
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


def set_execution_results(state, collation):
    """Set state root, receipt root, etc
    (ethereum.pow.common.set_execution_results)
    """
    collation.header.receipts_root = mk_receipt_sha(state.receipts)
    collation.header.tx_list_root = mk_transaction_sha(collation.transactions)

    # Notice: commit state before assigning
    state.commit()
    collation.header.post_state_root = state.trie.root_hash

    # TODO: Don't handle in basic sharding currently
    # block.header.gas_used = state.gas_used
    # block.header.bloom = state.bloom

    log.info('Collation pre-sealed, %d gas used' % state.gas_used)


def validate_transaction_tree(collation):
    """Validate that the transaction list root is correct
    """
    if collation.header.tx_list_root != mk_transaction_sha(collation.transactions):
        raise ValueError("Transaction root mismatch: header %s computed %s, %d transactions" %
                         (encode_hex(collation.header.tx_list_root), encode_hex(mk_transaction_sha(collation.transactions)),
                          len(collation.transactions)))
    return True


def verify_execution_results(state, collation):
    """Verify the results by Merkle Proof
    """
    state.commit()
    if collation.header.tx_list_root != mk_transaction_sha(collation.transactions):
        raise ValueError('Transaction root mismatch: header %s computed %s' %
                         (encode_hex(collation.header.tx_list_root), encode_hex(mk_transaction_sha(collation.transactions))))
    if collation.header.post_state_root != state.trie.root_hash:
        raise ValueError('State root mismatch: header %s computed %s' %
                         (encode_hex(collation.header.post_state_root), encode_hex(state.trie.root_hash)))
    if collation.header.receipts_root != mk_receipt_sha(state.receipts):
        raise ValueError('Receipt root mismatch: header %s computed %s, computed %d, %d receipts' %
                         (encode_hex(collation.header.receipts_root), encode_hex(mk_receipt_sha(state.receipts)),
                          state.gas_used, len(state.receipts)))

    return True


def finalize(state, coinbase):
    """Apply rewards and commit."""
    delta = int(state.config['COLLATOR_REWARD'])
    state.delta_balance(coinbase, delta)
