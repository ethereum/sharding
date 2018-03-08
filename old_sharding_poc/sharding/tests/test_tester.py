import pytest
import logging

from ethereum.utils import encode_hex
from ethereum.slogging import get_logger
from ethereum import utils

from sharding.tools import tester
from sharding import validator_manager_utils
from sharding.config import sharding_config

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
        c.mine(sharding_config['SHUFFLING_CYCLE_LENGTH'])
    c.add_test_shard(shard_id)
    return c


def test_collate():
    shard_id = 1
    t = chain(shard_id)

    # Round 1
    t.tx(tester.k1, tester.a2, 1, data=b'', shard_id=shard_id)
    log.info('CURRENT HEAD:{}'.format(encode_hex(t.chain.shards[shard_id].head_hash)))
    assert t.chain.shards[shard_id].get_score(t.chain.shards[shard_id].head) == 0
    assert t.collate(shard_id, tester.k0)
    t.mine(5)
    log.info('CURRENT HEAD:{}'.format(encode_hex(t.chain.shards[shard_id].head_hash)))
    assert t.chain.shards[shard_id].get_score(t.chain.shards[shard_id].head) == 1

    # Clear tester
    expected_period_number = t.chain.get_expected_period_number()
    t.set_collation(shard_id, expected_period_number)

    # Round 2
    t.tx(tester.k2, tester.a3, 1, data=b'', shard_id=shard_id)
    assert t.collate(shard_id, tester.k0)
    t.mine(5)
    log.info('CURRENT HEAD:{}'.format(encode_hex(t.chain.shards[shard_id].head_hash)))
    assert t.chain.shards[shard_id].get_score(t.chain.shards[shard_id].head) == 2


def test_deposit_and_withdaw():
    shard_id = 2
    t = chain(shard_id, k0_deposit=False)
    # make validation code
    privkey = tester.k5
    valcode_addr = t.sharding_valcode_addr(privkey)
    # deposit
    t.sharding_deposit(privkey, valcode_addr)
    t.mine(sharding_config['SHUFFLING_CYCLE_LENGTH'])
    assert hex(utils.big_endian_to_int(valcode_addr)) == \
        validator_manager_utils.call_valmgr(t.head_state, 'sample', [shard_id])
    x = tester.ABIContract(t, validator_manager_utils.get_valmgr_ct(), validator_manager_utils.get_valmgr_addr())
    assert x.get_num_validators() == 1
    # withdraw
    t.sharding_withdraw(privkey, 0)
    assert 0 == int(validator_manager_utils.call_valmgr(t.head_state, 'sample', [0]), 16)
    assert x.get_num_validators() == 0


def test_call_constant_function():
    shard_id = 1
    t = chain(shard_id)

    # deploy on main chain
    x = t.contract("""
hello: public(num)
def __init__():
    self.hello = 100
def get_plus_one() -> num:
    self.hello += 1
    return self.hello
    """, language='viper')

    t.mine(1)

    # constant call
    assert x.get_plus_one(is_constant=True) == 101
    assert x.get_hello() == 100

    # tx call
    assert x.get_plus_one() == 101
    assert x.get_hello() == 101

    # deploy on shard chain
    y = t.contract("""
hello: public(num)
def __init__():
    self.hello = 100
def get_plus_one() -> num:
    self.hello += 1
    return self.hello
    """, language='viper', shard_id=shard_id)

    # Collate and mine
    assert t.collate(shard_id, tester.k0)
    t.mine(5)

    # Clear tester
    expected_period_number = t.chain.get_expected_period_number()
    t.set_collation(shard_id, expected_period_number)

    # Constant call
    assert y.get_plus_one(is_constant=True, shard_id=shard_id) == 101
    assert y.get_hello() == 100

    # tx call
    assert y.get_plus_one() == 101
    assert y.get_hello() == 101
