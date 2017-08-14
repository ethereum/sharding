import pytest
import logging

from ethereum.slogging import get_logger
from ethereum.transaction_queue import TransactionQueue
from ethereum import utils
from ethereum import trie

from sharding import collator
from sharding.tools import tester

log = get_logger('test.collator')
log.setLevel(logging.DEBUG)


@pytest.fixture(scope='function')
def chain(shard_id):
    t = tester.Chain(env='sharding')
    t.mine(5)
    t.add_test_shard(shard_id)
    return t


def test_create_collation_empty_txqueue():
    """Test create_collation without transactions
    """
    shard_id = 1
    t = chain(shard_id)

    prev_collation_hash = t.chain.shards[shard_id].head_hash
    expected_period_number = t.chain.get_expected_period_number()

    txqueue = TransactionQueue()
    collation = collator.create_collation(
        t.chain,
        shard_id,
        prev_collation_hash,
        expected_period_number,
        coinbase=tester.a1,
        key=tester.k1,
        txqueue=txqueue)

    assert collation.transaction_count == 0
    assert collation.header.coinbase == tester.a1

    # sign error
    with pytest.raises(TypeError):
        collation = collator.create_collation(
            t.chain,
            shard_id,
            prev_collation_hash,
            expected_period_number,
            coinbase=tester.a1,
            key=123,
            txqueue=txqueue)


def test_create_collation_with_txs():
    """Test create_collation with transactions
    """
    shard_id = 1
    t = chain(shard_id)

    prev_collation_hash = t.chain.shards[shard_id].head_hash
    expected_period_number = t.chain.get_expected_period_number()

    txqueue = TransactionQueue()
    tx1 = t.generate_shard_tx(shard_id, tester.k2, tester.a4, int(0.03 * utils.denoms.ether))
    tx2 = t.generate_shard_tx(shard_id, tester.k3, tester.a5, int(0.03 * utils.denoms.ether))
    txqueue.add_transaction(tx1)
    txqueue.add_transaction(tx2)

    collation = collator.create_collation(
        t.chain,
        shard_id,
        prev_collation_hash,
        expected_period_number,
        coinbase=tester.a1,
        key=tester.k1,
        txqueue=txqueue)
    assert collation.transaction_count == 2


def test_apply_collation():
    """Apply collation to ShardChain
    """
    shard_id = 1
    t = chain(shard_id)

    txqueue = TransactionQueue()
    tx1 = t.generate_shard_tx(shard_id, tester.k2, tester.a4, int(0.03 * utils.denoms.ether))
    tx2 = t.generate_shard_tx(shard_id, tester.k3, tester.a5, int(0.03 * utils.denoms.ether))
    txqueue.add_transaction(tx1)
    txqueue.add_transaction(tx2)

    state = t.chain.shards[shard_id].state
    prev_state_root = state.trie.root_hash
    collation = t.generate_collation(shard_id=1, coinbase=tester.a1, key=tester.k1, txqueue=txqueue)
    period_start_prevblock = t.chain.get_block(collation.header.period_start_prevhash)

    collator.apply_collation(state, collation, period_start_prevblock)

    assert state.trie.root_hash != prev_state_root
    assert collation.header.post_state_root == state.trie.root_hash
    assert collation.header.post_state_root == t.chain.shards[shard_id].state.trie.root_hash


def test_apply_collation_wrong_root():
    """Test apply_collation with wrong roots in header
    test verify_execution_results
    """
    shard_id = 1
    t = chain(shard_id)

    # test 1 - arrange
    state = t.chain.shards[shard_id].state
    txqueue = TransactionQueue()
    tx1 = t.generate_shard_tx(shard_id, tester.k2, tester.a4, int(0.03 * utils.denoms.ether))
    txqueue.add_transaction(tx1)
    # post_state_root
    collation = t.generate_collation(shard_id=1, coinbase=tester.a1, key=tester.k1, txqueue=txqueue)
    period_start_prevblock = t.chain.get_block(collation.header.period_start_prevhash)
    # Set wrong root
    collation.header.post_state_root = trie.BLANK_ROOT
    with pytest.raises(ValueError):
        collator.apply_collation(state, collation, period_start_prevblock)

    # test 2 - arrange
    state = t.chain.shards[shard_id].state
    txqueue = TransactionQueue()
    tx1 = t.generate_shard_tx(shard_id, tester.k2, tester.a4, int(0.03 * utils.denoms.ether))
    txqueue.add_transaction(tx1)
    # receipts_root
    collation = t.generate_collation(shard_id=1, coinbase=tester.a1, key=tester.k1, txqueue=txqueue)
    period_start_prevblock = t.chain.get_block(collation.header.period_start_prevhash)
    # Set wrong root
    collation.header.receipts_root = trie.BLANK_ROOT
    with pytest.raises(ValueError):
        collator.apply_collation(state, collation, period_start_prevblock)

    # test 3 - arrange
    state = t.chain.shards[shard_id].state
    txqueue = TransactionQueue()
    tx1 = t.generate_shard_tx(shard_id, tester.k2, tester.a4, int(0.03 * utils.denoms.ether))
    txqueue.add_transaction(tx1)
    # receipts_root
    collation = t.generate_collation(shard_id=1, coinbase=tester.a1, key=tester.k1, txqueue=txqueue)
    period_start_prevblock = t.chain.get_block(collation.header.period_start_prevhash)
    # Set wrong root
    collation.header.tx_list_root = trie.BLANK_ROOT
    with pytest.raises(ValueError):
        collator.apply_collation(state, collation, period_start_prevblock)


def test_sign():
    """Test collator.sign(msg_hash, privkey)
    """
    msg_hash = utils.sha3('hello')
    privkey = tester.k0
    assert collator.sign(msg_hash, privkey) == b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x1bz\x05\x13\xf6\xa4\xbb\x0c\xaf<\x87\x95\xa7\xf5\x139\x84\x89\\#\x91\x15\x9dPX\x9e\xc9\x01\x8fp\x14\xd2,\x0c\x97\xd6\xbf\xc9\x11\x9d\xf7Z\x99-\xd3\x05\xc6\xf3\xfc\xfbe\x99c1\xcb\x93K\xf0I,\xd7\xebUB%'

    msg_hash2 = utils.sha3('world')
    assert collator.sign(msg_hash2, privkey) != b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x1bz\x05\x13\xf6\xa4\xbb\x0c\xaf<\x87\x95\xa7\xf5\x139\x84\x89\\#\x91\x15\x9dPX\x9e\xc9\x01\x8fp\x14\xd2,\x0c\x97\xd6\xbf\xc9\x11\x9d\xf7Z\x99-\xd3\x05\xc6\xf3\xfc\xfbe\x99c1\xcb\x93K\xf0I,\xd7\xebUB%'


def test_verify_collation_header():
    shard_id = 1
    t = chain(shard_id)

    prev_collation_hash = t.chain.shards[shard_id].head_hash
    expected_period_number = t.chain.get_expected_period_number()

    txqueue = TransactionQueue()
    tx1 = t.generate_shard_tx(shard_id, tester.k2, tester.a4, int(0.03 * utils.denoms.ether))
    tx2 = t.generate_shard_tx(shard_id, tester.k3, tester.a5, int(0.03 * utils.denoms.ether))
    txqueue.add_transaction(tx1)
    txqueue.add_transaction(tx2)

    collation = collator.create_collation(
        t.chain,
        shard_id,
        prev_collation_hash,
        expected_period_number,
        coinbase=tester.a1,
        key=tester.k1,
        txqueue=txqueue)
    assert collator.verify_collation_header(t.chain, collation.header)

    # Bad collation header 1
    collation = collator.create_collation(
        t.chain,
        shard_id,
        prev_collation_hash,
        expected_period_number,
        coinbase=tester.a1,
        key=tester.k1,
        txqueue=txqueue)
    collation.header.shard_id = -1
    with pytest.raises(ValueError):
        collator.verify_collation_header(t.chain, collation.header)

    # Bad collation header 2
    collation = collator.create_collation(
        t.chain,
        shard_id,
        prev_collation_hash,
        expected_period_number,
        coinbase=tester.a1,
        key=tester.k1,
        txqueue=txqueue)
    collation.header.expected_period_number = 100
    with pytest.raises(ValueError):
        collator.verify_collation_header(t.chain, collation.header)


    # TODO: more tests
