import pytest
import logging

from ethereum.state import State
from ethereum.transaction_queue import TransactionQueue
from ethereum import utils
from ethereum.slogging import get_logger
from ethereum.common import mk_transaction_sha, mk_receipt_sha
from ethereum import trie

from sharding.collation import Collation, CollationHeader
from sharding import state_transition
from sharding.tools import tester

log = get_logger('test.shard_chain')
log.setLevel(logging.DEBUG)

shard_id = 1


@pytest.fixture(scope='function')
def chain(shard_id):
    t = tester.Chain(env='sharding')
    t.mine(5)
    t.add_test_shard(shard_id)
    return t


def test_mk_collation_from_prevstate():
    """Test mk_collation_from_prevstate(shard_chain, state, coinbase)
    """
    t = chain(shard_id)
    coinbase = tester.a1
    state = t.chain.shards[shard_id].state
    collation = state_transition.mk_collation_from_prevstate(t.chain.shards[shard_id], state, coinbase)

    assert collation.hash is not None
    assert collation.header.shard_id == 1
    assert collation.header.prev_state_root == state.trie.root_hash
    assert collation.header.coinbase == coinbase
    assert not collation.transactions


def test_add_transactions():
    """Test add_transactions(state, collation, txqueue, min_gasprice=0)
    """
    t = chain(shard_id)
    tx1 = t.generate_shard_tx(shard_id, tester.k2, tester.a4, int(0.03 * utils.denoms.ether))
    tx2 = t.generate_shard_tx(shard_id, tester.k3, tester.a5, int(0.03 * utils.denoms.ether))
    txqueue = TransactionQueue()
    txqueue.add_transaction(tx1)
    txqueue.add_transaction(tx2)

    coinbase = tester.a1
    state = t.chain.shards[shard_id].state.ephemeral_clone()
    collation = state_transition.mk_collation_from_prevstate(t.chain.shards[shard_id], state, coinbase)

    state_transition.add_transactions(state, collation, txqueue, shard_id, mainchain_state=t.head_state)
    assert collation.transaction_count == 2
    assert state.get_balance(tester.a4) == 1000 * utils.denoms.ether + int(0.03 * utils.denoms.ether)

    # InsufficientBalance -> don't include this transaction
    tx3 = t.generate_shard_tx(shard_id, tester.k2, tester.a4, int(100000000000 * utils.denoms.ether))
    txqueue.add_transaction(tx3)
    state_transition.add_transactions(state, collation, txqueue, shard_id, mainchain_state=t.head_state)
    assert collation.transaction_count == 2


def test_update_collation_env_variables():
    """Test update_collation_env_variables(state, collation)
    """
    collation = Collation(CollationHeader(coinbase=tester.a2))
    state = State()
    state_transition.update_collation_env_variables(state, collation)
    assert state.block_coinbase == tester.a2


def test_set_execution_results():
    """Test set_execution_results(state, collation)
    """
    collation = Collation(CollationHeader(coinbase=tester.a2))
    state = State()
    state_transition.set_execution_results(state, collation)
    assert collation.header.receipts_root == mk_receipt_sha(state.receipts)
    assert collation.header.tx_list_root == mk_transaction_sha(collation.transactions)
    assert collation.header.post_state_root == state.trie.root_hash


def test_validate_transaction_tree():
    """Test validate_transaction_tree(collation)
    """
    t = chain(shard_id)
    tx1 = t.generate_shard_tx(shard_id, tester.k2, tester.a4, int(0.03 * utils.denoms.ether))
    tx2 = t.generate_shard_tx(shard_id, tester.k3, tester.a5, int(0.03 * utils.denoms.ether))
    txqueue = TransactionQueue()
    txqueue.add_transaction(tx1)
    txqueue.add_transaction(tx2)

    collation = t.generate_collation(shard_id=1, coinbase=tester.a1, key=tester.k1, txqueue=txqueue)
    assert state_transition.validate_transaction_tree(collation)

    collation.header.tx_list_root = trie.BLANK_ROOT
    with pytest.raises(ValueError):
        state_transition.validate_transaction_tree(collation)


def test_finalize():
    """Test finalize(state, coinbase)
    """
    coinbase = '\x35'*20
    t = chain(shard_id)
    state = t.chain.shards[shard_id].state
    state_transition.finalize(state, coinbase)
    assert state.get_balance(coinbase) == int(state.config['COLLATOR_REWARD'])
