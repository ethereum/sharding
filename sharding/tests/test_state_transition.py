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

shardId = 1


@pytest.fixture(scope='function')
def chain(shardId):
    t = tester.Chain(env='sharding')
    t.add_test_shard(shardId)
    t.mine(5)
    return t


def test_mk_collation_from_prevstate():
    """Test mk_collation_from_prevstate(shard_chain, state, coinbase)
    """
    t = chain(shardId)
    coinbase = tester.a1
    state = t.chain.shards[shardId].state
    collation = state_transition.mk_collation_from_prevstate(t.chain.shards[shardId], state, coinbase)

    assert collation.hash is not None
    assert collation.header.shardId == 1
    assert collation.header.prev_state_root == state.trie.root_hash
    assert collation.header.coinbase == coinbase
    assert not collation.transactions


def test_add_transactions():
    """Test add_transactions(state, collation, txqueue, min_gasprice=0)
    """
    t = chain(shardId)
    tx1 = t.generate_shard_tx(tester.k2, tester.a4, int(0.03 * utils.denoms.ether))
    tx2 = t.generate_shard_tx(tester.k3, tester.a5, int(0.03 * utils.denoms.ether))
    txqueue = TransactionQueue()
    txqueue.add_transaction(tx1)
    txqueue.add_transaction(tx2)

    coinbase = tester.a1
    state = t.chain.shards[shardId].state.ephemeral_clone()
    collation = state_transition.mk_collation_from_prevstate(t.chain.shards[shardId], state, coinbase)

    state_transition.add_transactions(state, collation, txqueue)
    assert collation.transaction_count == 2
    assert state.get_balance(tester.a4) == 1 * utils.denoms.ether + int(0.03 * utils.denoms.ether)


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
    t = chain(shardId)
    tx1 = t.generate_shard_tx(tester.k2, tester.a4, int(0.03 * utils.denoms.ether))
    tx2 = t.generate_shard_tx(tester.k3, tester.a5, int(0.03 * utils.denoms.ether))
    txqueue = TransactionQueue()
    txqueue.add_transaction(tx1)
    txqueue.add_transaction(tx2)

    collation = t.generate_collation(shardId=1, coinbase=tester.a1, txqueue=txqueue)
    assert state_transition.validate_transaction_tree(collation)

    collation.header.tx_list_root = trie.BLANK_ROOT
    with pytest.raises(ValueError):
        state_transition.validate_transaction_tree(collation)


def test_finalize():
    """Test finalize(state, coinbase)
    """
    coinbase = '\x35'*20
    t = chain(shardId)
    state = t.chain.shards[shardId].state
    state_transition.finalize(state, coinbase)
    assert state.get_balance(coinbase) == int(state.config['COLLATOR_REWARD'])
