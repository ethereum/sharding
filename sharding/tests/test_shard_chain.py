import pytest
import logging

from ethereum.utils import encode_hex
from ethereum.slogging import get_logger
from ethereum.transaction_queue import TransactionQueue
from ethereum import utils

from sharding.tools import tester


log = get_logger('test.shard_chain')
log.setLevel(logging.DEBUG)


@pytest.fixture(scope='function')
def chain(shardId):
    t = tester.Chain(env='sharding')
    t.add_test_shard(shardId)
    t.mine(5)
    return t


def test_add_collation():
    """Test add_collation(self, collation, period_start_prevblock, handle_orphan_collation)
    """
    shardId = 1
    t = tester.Chain(env='sharding')
    t.chain.init_shard(shardId)
    t.mine(5)

    # parent = empty
    collation1 = t.generate_collation(shardId=1, coinbase=tester.a1, txqueue=None)
    period_start_prevblock = t.chain.get_block(collation1.header.period_start_prevhash)
    t.chain.shards[shardId].add_collation(collation1, period_start_prevblock, t.chain.handle_orphan_collation)
    assert t.chain.shards[shardId].get_score(collation1) == 1
    # parent = empty
    collation2 = t.generate_collation(shardId=1, coinbase=tester.a2, txqueue=None)
    period_start_prevblock = t.chain.get_block(collation2.header.period_start_prevhash)
    t.chain.shards[shardId].add_collation(collation2, period_start_prevblock, t.chain.handle_orphan_collation)
    assert t.chain.shards[shardId].get_score(collation2) == 1
    # parent = collation1
    collation3 = t.generate_collation(shardId=1, coinbase=tester.a2, txqueue=None, prev_collation_hash=collation1.header.hash)
    period_start_prevblock = t.chain.get_block(collation3.header.period_start_prevhash)
    t.chain.shards[shardId].add_collation(collation3, period_start_prevblock, t.chain.handle_orphan_collation)
    assert t.chain.shards[shardId].get_score(collation3) == 2
    # parent = collation3
    collation4 = t.generate_collation(shardId=1, coinbase=tester.a2, txqueue=None, prev_collation_hash=collation3.header.hash)
    period_start_prevblock = t.chain.get_block(collation4.header.period_start_prevhash)
    t.chain.shards[shardId].add_collation(collation4, period_start_prevblock, t.chain.handle_orphan_collation)
    assert t.chain.shards[shardId].get_score(collation4) == 3


def test_handle_orphan_collation():
    """Test handle_orphan_collation(self, collation, period_start_prevblock, handle_orphan_collation)
    """
    shardId = 1
    # Collator: create and apply collation sequentially
    t1 = tester.Chain(env='sharding')
    t1.chain.init_shard(shardId)
    t1.mine(5)
    # collation1
    collation1 = t1.generate_collation(shardId=1, coinbase=tester.a1, txqueue=None)
    period_start_prevblock = t1.chain.get_block(collation1.header.period_start_prevhash)
    t1.chain.shards[shardId].add_collation(collation1, period_start_prevblock, t1.chain.handle_orphan_collation)
    assert t1.chain.shards[shardId].get_score(collation1) == 1
    # collation2
    collation2 = t1.generate_collation(shardId=1, coinbase=tester.a2, txqueue=None, prev_collation_hash=collation1.header.hash)
    period_start_prevblock = t1.chain.get_block(collation2.header.period_start_prevhash)
    t1.chain.shards[shardId].add_collation(collation2, period_start_prevblock, t1.chain.handle_orphan_collation)
    assert t1.chain.shards[shardId].get_score(collation2) == 2
    # collation3
    collation3 = t1.generate_collation(shardId=1, coinbase=tester.a2, txqueue=None, prev_collation_hash=collation2.header.hash)
    period_start_prevblock = t1.chain.get_block(collation3.header.period_start_prevhash)
    t1.chain.shards[shardId].add_collation(collation3, period_start_prevblock, t1.chain.handle_orphan_collation)
    assert t1.chain.shards[shardId].get_score(collation3) == 3

    # Validator: apply collation2, collation3 and collation1
    t2 = tester.Chain(env='sharding')
    t2.chain.init_shard(shardId)
    t2.mine(5)
    # append collation2
    t2.chain.shards[shardId].add_collation(collation2, period_start_prevblock, t2.chain.handle_orphan_collation)
    # append collation3
    t2.chain.shards[shardId].add_collation(collation3, period_start_prevblock, t2.chain.handle_orphan_collation)
    # append collation1 now
    t2.chain.shards[shardId].add_collation(collation1, period_start_prevblock, t2.chain.handle_orphan_collation)
    assert t2.chain.shards[shardId].get_score(collation1) == 1
    assert t2.chain.shards[shardId].get_score(collation2) == 2
    assert t2.chain.shards[shardId].get_score(collation3) == 3


def test_transaction():
    """Test create and apply collation with transactions
    """
    shardId = 1
    t = chain(shardId)
    log.info('head state: {}'.format(encode_hex(t.chain.shards[shardId].state.trie.root_hash)))

    tx1 = t.generate_shard_tx(tester.k2, tester.a4, int(0.03 * utils.denoms.ether))
    tx2 = t.generate_shard_tx(tester.k3, tester.a5, int(0.03 * utils.denoms.ether))

    # Prepare txqueue
    txqueue = TransactionQueue()
    txqueue.add_transaction(tx1)
    txqueue.add_transaction(tx2)

    collation = t.generate_collation(shardId=1, coinbase=tester.a1, txqueue=txqueue)
    log.info('collation: {}, transaction_count:{}'.format(collation.to_dict(), collation.transaction_count))

    period_start_prevblock = t.chain.get_block(collation.header.period_start_prevhash)
    log.info('period_start_prevblock: {}'.format(encode_hex(period_start_prevblock.header.hash)))

    t.chain.shards[shardId].add_collation(collation, period_start_prevblock, t.chain.handle_orphan_collation)
    log.info('state: {}'.format(encode_hex(t.chain.shards[shardId].state.trie.root_hash)))

    # Check to addesss received value
    assert t.chain.shards[shardId].state.get_balance(tester.a4) == 1030000000000000000

    # Check incentives
    assert t.chain.shards[shardId].state.get_balance(tester.a1) == 1002000000000000000


def test_get_collation():
    """Test get_parent(self, collation)
    """
    shardId = 1
    t = tester.Chain(env='sharding')

    t.chain.init_shard(shardId)
    t.mine(5)

    collation = t.generate_collation(shardId=1, coinbase=tester.a1, txqueue=None)
    period_start_prevblock = t.chain.get_block(collation.header.period_start_prevhash)
    t.chain.shards[shardId].add_collation(collation, period_start_prevblock, t.chain.handle_orphan_collation)

    assert t.chain.shards[shardId].get_collation(collation.header.hash).header.hash == collation.header.hash


def test_get_parent():
    """Test get_parent(self, collation)
    """
    t = tester.Chain(env='sharding')
    shardId = 1
    t.chain.init_shard(shardId)
    t.mine(5)

    collation = t.generate_collation(shardId=1, coinbase=tester.a1, txqueue=None)
    period_start_prevblock = t.chain.get_block(collation.header.period_start_prevhash)
    t.chain.shards[shardId].add_collation(collation, period_start_prevblock, t.chain.handle_orphan_collation)
    assert t.chain.shards[shardId].is_first_collation(collation)
    # append to previous collation
    collation = t.generate_collation(shardId=1, coinbase=tester.a1, txqueue=None, prev_collation_hash=collation.header.hash)
    period_start_prevblock = t.chain.get_block(collation.header.period_start_prevhash)
    t.chain.shards[shardId].add_collation(collation, period_start_prevblock, t.chain.handle_orphan_collation)
    assert not t.chain.shards[shardId].is_first_collation(collation)
    assert t.chain.shards[shardId].get_parent(collation).header.hash == collation.header.parent_collation_hash


# TODO: after add_block
# def test_get_head_collation():
#     """Test get_head_collation(blockhash)
#     """
#     shardId = 1
#     t = chain(shardId)
#     tx1 = t.generate_shard_tx(tester.k2, tester.a4, int(0.03 * utils.denoms.ether))
#     txqueue = TransactionQueue()
#     txqueue.add_transaction(tx1)

#     collation = t.generate_collation(shardId=1, coinbase=tester.a1, txqueue=txqueue)
#     period_start_prevblock = t.chain.get_block(collation.header.period_start_prevhash)
#     t.chain.shards[shardId].add_collation(collation, period_start_prevblock, t.chain.handle_orphan_collation)
#     log.info('state: {}'.format(encode_hex(t.chain.shards[shardId].state.trie.root_hash)))

#     blockhash = t.chain.head_hash
#     #  print('head_collation: %s' % encode_hex(t.chain.shards[shardId].get_head_collation(blockhash).header.hash))
#     assert t.chain.shards[shardId].get_head_collation(blockhash) is not None
