import pytest

from ethereum.transaction_queue import TransactionQueue
from ethereum import utils
from ethereum import trie

from sharding import collator
from sharding.tools import tester


@pytest.fixture(scope='function')
def chain(shardId):
    t = tester.Chain(env='sharding')
    t.add_test_shard(shardId)
    t.mine(5)
    return t


def test_create_collation_empty_txqueue():
    """Test create_collation without transactions
    """
    shardId = 1
    t = chain(shardId)

    prev_collation_hash = t.chain.shards[shardId].head_hash
    expected_period_number = t.chain.get_expected_period_number()

    txqueue = TransactionQueue()
    collation = collator.create_collation(
        t.chain,
        shardId,
        prev_collation_hash,
        expected_period_number,
        coinbase=tester.a1,
        key=tester.k1,
        txqueue=txqueue)

    assert collation.transaction_count == 0
    assert collation.header.coinbase == tester.a1


def test_create_collation_with_txs():
    """Test create_collation with transactions
    """
    shardId = 1
    t = chain(shardId)

    prev_collation_hash = t.chain.shards[shardId].head_hash
    expected_period_number = t.chain.get_expected_period_number()

    txqueue = TransactionQueue()
    tx1 = t.generate_shard_tx(tester.k2, tester.a4, int(0.03 * utils.denoms.ether))
    tx2 = t.generate_shard_tx(tester.k3, tester.a5, int(0.03 * utils.denoms.ether))
    txqueue.add_transaction(tx1)
    txqueue.add_transaction(tx2)

    collation = collator.create_collation(
        t.chain,
        shardId,
        prev_collation_hash,
        expected_period_number,
        coinbase=tester.a1,
        key=tester.k1,
        txqueue=txqueue)
    assert collation.transaction_count == 2


def test_apply_collation():
    """Apply collation to ShardChain
    """
    shardId = 1
    t = chain(shardId)

    txqueue = TransactionQueue()
    tx1 = t.generate_shard_tx(tester.k2, tester.a4, int(0.03 * utils.denoms.ether))
    tx2 = t.generate_shard_tx(tester.k3, tester.a5, int(0.03 * utils.denoms.ether))
    txqueue.add_transaction(tx1)
    txqueue.add_transaction(tx2)

    state = t.chain.shards[shardId].state
    prev_state_root = state.trie.root_hash
    collation = t.generate_collation(shardId=1, coinbase=tester.a1, key=tester.k1, txqueue=txqueue)
    period_start_prevblock = t.chain.get_block(collation.header.period_start_prevhash)

    collator.apply_collation(state, collation, period_start_prevblock)

    assert state.trie.root_hash != prev_state_root
    assert collation.header.post_state_root == state.trie.root_hash
    assert collation.header.post_state_root == t.chain.shards[shardId].state.trie.root_hash


def test_apply_collation_wrong_root():
    """Test apply_collation with wrong roots in header
    test verify_execution_results
    """
    shardId = 1
    t = chain(shardId)

    # test 1 - arrange
    state = t.chain.shards[shardId].state
    txqueue = TransactionQueue()
    tx1 = t.generate_shard_tx(tester.k2, tester.a4, int(0.03 * utils.denoms.ether))
    txqueue.add_transaction(tx1)
    # post_state_root
    collation = t.generate_collation(shardId=1, coinbase=tester.a1, key=tester.k1, txqueue=txqueue)
    period_start_prevblock = t.chain.get_block(collation.header.period_start_prevhash)
    # Set wrong root
    collation.header.post_state_root = trie.BLANK_ROOT
    with pytest.raises(ValueError):
        collator.apply_collation(state, collation, period_start_prevblock)

    # test 2 - arrange
    state = t.chain.shards[shardId].state
    txqueue = TransactionQueue()
    tx1 = t.generate_shard_tx(tester.k2, tester.a4, int(0.03 * utils.denoms.ether))
    txqueue.add_transaction(tx1)
    # receipts_root
    collation = t.generate_collation(shardId=1, coinbase=tester.a1, key=tester.k1, txqueue=txqueue)
    period_start_prevblock = t.chain.get_block(collation.header.period_start_prevhash)
    # Set wrong root
    collation.header.receipts_root = trie.BLANK_ROOT
    with pytest.raises(ValueError):
        collator.apply_collation(state, collation, period_start_prevblock)

    # test 3 - arrange
    state = t.chain.shards[shardId].state
    txqueue = TransactionQueue()
    tx1 = t.generate_shard_tx(tester.k2, tester.a4, int(0.03 * utils.denoms.ether))
    txqueue.add_transaction(tx1)
    # receipts_root
    collation = t.generate_collation(shardId=1, coinbase=tester.a1, key=tester.k1, txqueue=txqueue)
    period_start_prevblock = t.chain.get_block(collation.header.period_start_prevhash)
    # Set wrong root
    collation.header.tx_list_root = trie.BLANK_ROOT
    with pytest.raises(ValueError):
        collator.apply_collation(state, collation, period_start_prevblock)
