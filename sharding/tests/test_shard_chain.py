import pytest
import logging

from ethereum.utils import encode_hex
from ethereum.slogging import get_logger
from ethereum.transaction_queue import TransactionQueue
from ethereum import utils
from ethereum import trie

from sharding.tools import tester
from sharding.shard_chain import ShardChain

log = get_logger('test.shard_chain')
log.setLevel(logging.DEBUG)


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


def test_add_collation():
    """Test add_collation(self, collation, period_start_prevblock, handle_ignored_collation)
    """
    shard_id = 1
    t = tester.Chain(env='sharding')
    t.chain.init_shard(shard_id)
    t.mine(5)

    # parent = empty
    collation1 = t.generate_collation(shard_id=1, coinbase=tester.a1, key=tester.k1, txqueue=None)
    period_start_prevblock = t.chain.get_block(collation1.header.period_start_prevhash)
    t.chain.shards[shard_id].add_collation(collation1, period_start_prevblock, t.chain.handle_ignored_collation)
    assert t.chain.shards[shard_id].get_score(collation1) == 1
    # parent = empty
    collation2 = t.generate_collation(shard_id=1, coinbase=tester.a2, key=tester.k1, txqueue=None)
    period_start_prevblock = t.chain.get_block(collation2.header.period_start_prevhash)
    t.chain.shards[shard_id].add_collation(collation2, period_start_prevblock, t.chain.handle_ignored_collation)
    assert t.chain.shards[shard_id].get_score(collation2) == 1
    # parent = collation1
    collation3 = t.generate_collation(shard_id=1, coinbase=tester.a2, key=tester.k1, txqueue=None, parent_collation_hash=collation1.header.hash)
    period_start_prevblock = t.chain.get_block(collation3.header.period_start_prevhash)
    t.chain.shards[shard_id].add_collation(collation3, period_start_prevblock, t.chain.handle_ignored_collation)
    assert t.chain.shards[shard_id].get_score(collation3) == 2
    # parent = collation3
    collation4 = t.generate_collation(shard_id=1, coinbase=tester.a2, key=tester.k1, txqueue=None, parent_collation_hash=collation3.header.hash)
    period_start_prevblock = t.chain.get_block(collation4.header.period_start_prevhash)
    t.chain.shards[shard_id].add_collation(collation4, period_start_prevblock, t.chain.handle_ignored_collation)
    assert t.chain.shards[shard_id].get_score(collation4) == 3


def test_add_collation_error():
    """Test add_collation(self, collation, period_start_prevblock, handle_ignored_collation)
    """
    shard_id = 1
    t = tester.Chain(env='sharding')
    t.chain.init_shard(shard_id)
    t.mine(5)

    # parent = empty
    collation1 = t.generate_collation(shard_id=1, coinbase=tester.a1, key=tester.k1, txqueue=None)
    period_start_prevblock = t.chain.get_block(collation1.header.period_start_prevhash)
    t.chain.shards[shard_id].add_collation(collation1, period_start_prevblock, t.chain.handle_ignored_collation)

    # parent = collation1
    collation2 = t.generate_collation(shard_id=1, coinbase=tester.a2, key=tester.k1, txqueue=None, parent_collation_hash=collation1.header.hash)
    period_start_prevblock = t.chain.get_block(collation2.header.period_start_prevhash)

    collation2.header.post_state_root = trie.BLANK_ROOT

    # apply_collation error
    assert not t.chain.shards[shard_id].add_collation(collation2, period_start_prevblock, t.chain.handle_ignored_collation)


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


def test_transaction():
    """Test create and apply collation with transactions
    """
    shard_id = 1
    t = chain(shard_id)
    log.info('head state: {}'.format(encode_hex(t.chain.shards[shard_id].state.trie.root_hash)))

    tx1 = t.generate_shard_tx(shard_id, tester.k2, tester.a4, int(0.03 * utils.denoms.ether))
    tx2 = t.generate_shard_tx(shard_id, tester.k3, tester.a5, int(0.03 * utils.denoms.ether))

    # Prepare txqueue
    txqueue = TransactionQueue()
    txqueue.add_transaction(tx1)
    txqueue.add_transaction(tx2)

    collation = t.generate_collation(shard_id=1, coinbase=tester.a1, key=tester.k1, txqueue=txqueue)
    log.debug('collation: {}, transaction_count:{}'.format(collation.to_dict(), collation.transaction_count))

    period_start_prevblock = t.chain.get_block(collation.header.period_start_prevhash)
    log.debug('period_start_prevblock: {}'.format(encode_hex(period_start_prevblock.header.hash)))
    t.chain.shards[shard_id].add_collation(collation, period_start_prevblock, t.chain.handle_ignored_collation)

    state = t.chain.shards[shard_id].mk_poststate_of_collation_hash(collation.header.hash)

    # Check to addesss received value
    assert state.get_balance(tester.a4) == 1000030000000000000000
    # Check incentives
    assert state.get_balance(tester.a1) == 1000002000000000000000

    # mk_poststate_of_collation_hash error
    with pytest.raises(Exception):
        state = t.chain.shards[shard_id].mk_poststate_of_collation_hash(b'1234')


def test_get_collation():
    """Test get_parent(self, collation)
    """
    shard_id = 1
    t = tester.Chain(env='sharding')

    t.chain.init_shard(shard_id)
    t.mine(5)

    collation = t.generate_collation(shard_id=1, coinbase=tester.a1, key=tester.k1, txqueue=None)
    period_start_prevblock = t.chain.get_block(collation.header.period_start_prevhash)
    t.chain.shards[shard_id].add_collation(collation, period_start_prevblock, t.chain.handle_ignored_collation)

    assert t.chain.shards[shard_id].get_collation(collation.header.hash).header.hash == collation.header.hash


def test_get_parent():
    """Test get_parent(self, collation)
    """
    t = tester.Chain(env='sharding')
    shard_id = 1
    t.chain.init_shard(shard_id)
    t.mine(5)

    collation = t.generate_collation(shard_id=1, coinbase=tester.a1, key=tester.k1, txqueue=None)
    period_start_prevblock = t.chain.get_block(collation.header.period_start_prevhash)
    t.chain.shards[shard_id].add_collation(collation, period_start_prevblock, t.chain.handle_ignored_collation)
    assert t.chain.shards[shard_id].is_first_collation(collation)

    # append to previous collation
    collation = t.generate_collation(shard_id=1, coinbase=tester.a1, key=tester.k1, txqueue=None, parent_collation_hash=collation.header.hash)
    period_start_prevblock = t.chain.get_block(collation.header.period_start_prevhash)
    t.chain.shards[shard_id].add_collation(collation, period_start_prevblock, t.chain.handle_ignored_collation)
    assert not t.chain.shards[shard_id].is_first_collation(collation)
    assert t.chain.shards[shard_id].get_parent(collation).header.hash == collation.header.parent_collation_hash


def test_cb_function():
    shard_id = 1
    t = tester.Chain(env='sharding')
    shard = ShardChain(shard_id=shard_id, new_head_cb=cb_function, env=t.chain.env)

    assert t.chain.add_shard(shard)
    t.mine(5)

    collation1 = t.generate_collation(shard_id=shard_id, coinbase=tester.a1, key=tester.k1, txqueue=None)
    period_start_prevblock = t.chain.get_block(collation1.header.period_start_prevhash)
    assert t.chain.shards[shard_id].add_collation(collation1, period_start_prevblock, t.chain.handle_ignored_collation)
    global cb_function_is_called
    assert cb_function_is_called


cb_function_is_called = False


def cb_function(collation):
    global cb_function_is_called
    cb_function_is_called = True
    log.debug('cb_function is called')
    return collation.header.hash
