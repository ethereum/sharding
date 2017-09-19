import pytest
import logging

from ethereum.slogging import get_logger
from ethereum.utils import encode_hex

from sharding.tools import tester
from sharding.shard_chain import ShardChain
from sharding.collation import Collation

log = get_logger('test.shard_chain')
log.setLevel(logging.DEBUG)


def test_init_shard():
    """Test init_shard(self, shard_id)
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
    shard_id = 1
    t = tester.Chain(env='sharding')
    shard = ShardChain(shard_id=shard_id)

    assert t.chain.add_shard(shard)
    assert len(t.chain.shard_id_list) == 1

    assert not t.chain.add_shard(shard)


def test_get_expected_period_number():
    """Test get_expected_period_number(self)
    """
    shard_id = 1
    t = tester.Chain(env='sharding')
    t.chain.init_shard(shard_id)

    t.mine(5)  # block number = 5
    assert t.chain.get_expected_period_number() == 1

    t.mine(4)  # block number = 9
    assert t.chain.get_expected_period_number() == 2

    t.mine(1)  # block number = 10
    assert t.chain.get_expected_period_number() == 2


def test_get_period_start_prevhash():
    """Test get_period_start_prevhash(self, expected_period_number)
    """
    shard_id = 1
    t = tester.Chain(env='sharding')
    t.chain.init_shard(shard_id)
    t.mine(5)

    expected_period_number = 1
    assert t.chain.get_period_start_prevhash(expected_period_number)

    expected_period_number = 2
    assert t.chain.get_period_start_prevhash(expected_period_number) is None


def test_handle_ignored_collation():
    """Test handle_ignored_collation(self, collation, period_start_prevblock, handle_ignored_collation)
    """
    shard_id = 1
    # Collator: create and apply collation sequentially
    t1 = tester.Chain(env='sharding')
    t1.chain.init_shard(shard_id)
    t1.mine(5)
    # collation1
    collation1 = t1.generate_collation(shard_id=1, coinbase=tester.a1, key=tester.k1, txqueue=None)
    period_start_prevblock = t1.chain.get_block(collation1.header.period_start_prevhash)
    t1.chain.shards[shard_id].add_collation(collation1, period_start_prevblock, t1.chain.handle_ignored_collation)
    assert t1.chain.shards[shard_id].get_score(collation1) == 1
    # collation2
    collation2 = t1.generate_collation(shard_id=1, coinbase=tester.a2, key=tester.k2, txqueue=None, parent_collation_hash=collation1.header.hash)
    period_start_prevblock = t1.chain.get_block(collation2.header.period_start_prevhash)
    t1.chain.shards[shard_id].add_collation(collation2, period_start_prevblock, t1.chain.handle_ignored_collation)
    assert t1.chain.shards[shard_id].get_score(collation2) == 2
    # collation3
    collation3 = t1.generate_collation(shard_id=1, coinbase=tester.a2, key=tester.k2, txqueue=None, parent_collation_hash=collation2.header.hash)
    period_start_prevblock = t1.chain.get_block(collation3.header.period_start_prevhash)
    t1.chain.shards[shard_id].add_collation(collation3, period_start_prevblock, t1.chain.handle_ignored_collation)
    assert t1.chain.shards[shard_id].get_score(collation3) == 3

    # Validator: apply collation2, collation3 and collation1
    t2 = tester.Chain(env='sharding')
    t2.chain.init_shard(shard_id)
    t2.mine(5)
    # append collation2
    t2.chain.shards[shard_id].add_collation(collation2, period_start_prevblock, t2.chain.handle_ignored_collation)
    # append collation3
    t2.chain.shards[shard_id].add_collation(collation3, period_start_prevblock, t2.chain.handle_ignored_collation)
    # append collation1 now
    t2.chain.shards[shard_id].add_collation(collation1, period_start_prevblock, t2.chain.handle_ignored_collation)
    assert t2.chain.shards[shard_id].get_score(collation1) == 1
    assert t2.chain.shards[shard_id].get_score(collation2) == 2
    assert t2.chain.shards[shard_id].get_score(collation3) == 3


@pytest.fixture(scope='function')
def chain(shard_id, k0_deposit=True):
    c = tester.Chain(env='sharding', deploy_sharding_contracts=True)
    c.mine(5)

    # make validation code
    privkey = tester.k0
    valcode_addr = c.sharding_valcode_addr(privkey)
    if k0_deposit:
        # deposit
        c.sharding_deposit(privkey, valcode_addr)
        c.mine(1)
    c.add_test_shard(shard_id)
    return c


def test_longest_chain_rule():
    # Initial chains
    shard_id = 1
    t = chain(shard_id)

    # [block 1]
    block_1 = t.mine(1)
    log.info('[block 1] CURRENT BLOCK HEAD:{}'.format(encode_hex(t.chain.head_hash)))

    # collate for the existing txs
    collation_0 = Collation(t.collate(shard_id, tester.k0))
    t.set_collation(
        shard_id,
        expected_period_number=collation_0.header.expected_period_number)

    # [block 2]: includes collation A -> B
    t.tx(tester.k1, tester.a2, 1, data=b'', shard_id=shard_id)
    collation_AB = Collation(t.collate(shard_id, tester.k0))
    block_2 = t.mine(5)
    log.info('[block 2] CURRENT BLOCK HEAD:{}'.format(encode_hex(t.chain.head_hash)))
    log.info('[block 2] CURRENT SHARD HEAD:{}'.format(encode_hex(t.chain.shards[shard_id].head_hash)))
    assert t.chain.shards[shard_id].get_score(t.chain.shards[shard_id].head) == 1

    # [block 2']: includes collation A -> B
    # Change main chain head
    t.change_head(block_1.hash)
    # Clear tester
    t.set_collation(
        shard_id,
        expected_period_number=collation_AB.header.expected_period_number,
        parent_collation_hash=collation_AB.header.parent_collation_hash)
    # tx of shard 1
    t.tx(tester.k1, tester.a2, 1, data=b'', shard_id=shard_id)
    collation_AB_2 = Collation(t.collate(shard_id, tester.k0))
    # tx of main chain
    t.tx(tester.k1, tester.a4, 1, data=b'')
    assert collation_AB.hash == collation_AB_2.hash
    t.mine(5)
    log.info('[block 2\'] CURRENT BLOCK HEAD:{}'.format(encode_hex(t.chain.head_hash)))
    log.info('[block 2\'] CURRENT SHARD HEAD:{}'.format(encode_hex(t.chain.shards[shard_id].head_hash)))
    assert t.chain.shards[shard_id].get_score(t.chain.shards[shard_id].head) == 1
    assert t.chain.get_score(t.chain.head) == 13

    # [block 3']: includes collation B -> C
    # Clear tester
    expected_period_number = t.chain.get_expected_period_number()
    t.set_collation(shard_id, expected_period_number)
    # tx of shard 1
    t.tx(tester.k1, tester.a2, 1, data=b'', shard_id=shard_id)
    # tx of main chain
    t.tx(tester.k1, tester.a4, 1, data=b'')
    collation_BC = Collation(t.collate(shard_id, tester.k0))
    t.mine(5)
    log.info('[block 3\'] CURRENT BLOCK HEAD:{}'.format(encode_hex(t.chain.head_hash)))
    log.info('[block 3\'] CURRENT SHARD HEAD:{}'.format(encode_hex(t.chain.shards[shard_id].head_hash)))
    assert t.chain.shards[shard_id].get_score(t.chain.shards[shard_id].head) == 2
    assert t.chain.get_score(t.chain.head) == 18
    assert t.chain.shards[shard_id].head_hash == collation_BC.hash

    # [block 3]: doesn't include collation
    # Change main chain head
    t.change_head(block_2.hash)
    t.mine(5)
    log.info('[block 3] CURRENT BLOCK HEAD:{}'.format(encode_hex(t.chain.head_hash)))
    log.info('[block 3] CURRENT SHARD HEAD:{}'.format(encode_hex(t.chain.shards[shard_id].head_hash)))
    assert t.chain.shards[shard_id].get_score(t.chain.shards[shard_id].head) == 2
    assert t.chain.get_score(t.chain.head) == 18
    assert t.chain.shards[shard_id].head_hash == collation_BC.hash

    # [block 4]: doesn't include collation
    t.mine(5)
    log.info('[block 4] CURRENT BLOCK HEAD:{}'.format(encode_hex(t.chain.head_hash)))
    log.info('[block 4] CURRENT SHARD HEAD:{}'.format(encode_hex(t.chain.shards[shard_id].head_hash)))
    assert t.chain.shards[shard_id].get_score(t.chain.shards[shard_id].head) == 1
    assert t.chain.get_score(t.chain.head) == 23
    assert t.chain.shards[shard_id].head_hash == collation_AB.hash
