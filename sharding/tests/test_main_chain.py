import pytest
import logging

from ethereum.slogging import get_logger

from sharding.tools import tester
from sharding.shard_chain import ShardChain

log = get_logger('test.shard_chain')
log.setLevel(logging.DEBUG)


@pytest.fixture(scope='function')
def chain(shardId):
    t = tester.Chain(env='sharding')
    t.add_test_shard(shardId)
    t.mine(5)
    return t


def test_init_shard():
    """Test init_shard(self, shardId)
    """
    t = tester.Chain(env='sharding')
    assert t.chain.init_shard(1)
    assert len(t.chain.shard_id_list) == 1

    assert t.chain.init_shard(2)
    assert len(t.chain.shard_id_list) == 2

    assert not t.chain.init_shard(2)
    assert len(t.chain.shard_id_list) == 2


def test_add_shard():
    """Test add_shard(self, shard)
    """
    shardId = 1
    t = tester.Chain(env='sharding')
    shard = ShardChain(shardId=shardId)

    assert t.chain.add_shard(shard)
    assert len(t.chain.shard_id_list) == 1

    assert not t.chain.add_shard(shard)


def test_get_expected_period_number():
    """Test get_expected_period_number(self)
    """
    shardId = 1
    t = tester.Chain(env='sharding')
    t.chain.init_shard(shardId)
    t.mine(5)

    assert t.chain.get_expected_period_number() == 2
    t.mine(4)
    assert t.chain.get_expected_period_number() == 2
    t.mine(1)
    assert t.chain.get_expected_period_number() == 3


def test_get_period_start_prevhash():
    """Test get_period_start_prevhash(self, expected_period_number)
    """
    shardId = 1
    t = tester.Chain(env='sharding')
    t.chain.init_shard(shardId)
    t.mine(5)

    expected_period_number = 1
    assert t.chain.get_period_start_prevhash(expected_period_number)

    expected_period_number = 2
    assert t.chain.get_period_start_prevhash(expected_period_number) is None


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
