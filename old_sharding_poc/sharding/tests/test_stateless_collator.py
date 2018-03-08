import pytest
import logging
import rlp

from ethereum.slogging import get_logger
from ethereum.transaction_queue import TransactionQueue

from sharding import collator
from sharding import stateless_collator
from sharding.collation import CollationHeader
from sharding.tools import tester
from sharding.config import sharding_config
from sharding.validator_manager_utils import call_tx_add_header

log = get_logger('test.collator')
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
        c.mine((sharding_config['SHUFFLING_CYCLE_LENGTH']))    # [TODO]: remove shuffling cycle
    c.add_test_shard(shard_id)
    return c


def apply_add_header(t, collation_header, privkey=tester.k0):
    tx = call_tx_add_header(
        t.head_state,
        privkey,
        0,
        rlp.encode(CollationHeader.serialize(collation_header)),
    )
    t.direct_tx(tx)


def test_get_collations_with_score():
    shard_id = 1
    t1 = chain(shard_id)

    # part 1: test get_collations_with_score

    # Create a collation with score = 1
    expected_period_number = t1.chain.get_expected_period_number()
    collation_1 = collator.create_collation(
        t1.chain,
        shard_id,
        parent_collation_hash=t1.chain.shards[shard_id].head_hash,
        expected_period_number=expected_period_number,
        coinbase=tester.a0,
        key=tester.k0,
        txqueue=TransactionQueue(),
        period_start_prevhash=t1.chain.get_period_start_prevhash(expected_period_number),
    )
    assert collation_1.number == 1
    apply_add_header(
        t1,
        collation_1.header,
        privkey=tester.k0,
    )

    assert stateless_collator.get_collations_with_score(t1.head_state, shard_id, 1) == \
        [collation_1.hash]

    t1.mine(5)

    # Create another collation with score = 1
    expected_period_number = t1.chain.get_expected_period_number()
    collation_2 = collator.create_collation(
        t1.chain,
        shard_id,
        parent_collation_hash=collation_1.parent_collation_hash,
        expected_period_number=expected_period_number,
        coinbase=tester.a0,
        key=tester.k0,
        txqueue=TransactionQueue(),
        period_start_prevhash=t1.chain.get_period_start_prevhash(expected_period_number),
    )
    assert collation_2.number == 1

    assert t1.chain.shards[shard_id].get_score(t1.chain.shards[shard_id].head) == 0
    period_start_prevblock = t1.chain.get_block(collation_2.header.period_start_prevhash)
    assert t1.chain.shards[shard_id].add_collation(collation_2, period_start_prevblock)
    assert t1.chain.shards[shard_id].get_score(collation_2) == 1

    apply_add_header(
        t1,
        collation_2.header,
        privkey=tester.k0,
    )

    t1.mine(5)

    # Check if there are two collations in collations_with_score[shard_id][score]
    assert collation_1.expected_period_number != collation_2.expected_period_number
    assert stateless_collator.get_collations_with_score(t1.head_state, shard_id, 1) == \
        [collation_1.hash, collation_2.hash]

    # part 2: test_get_collations_with_scores_in_range

    collations = stateless_collator.get_collations_with_scores_in_range(
        t1.head_state,
        shard_id,
        1,
        2,
    )
    assert len(collations) == 2

    # Create another collation with score = 2
    expected_period_number = t1.chain.get_expected_period_number()
    collation_3 = collator.create_collation(
        t1.chain,
        shard_id,
        parent_collation_hash=collation_2.hash,
        expected_period_number=expected_period_number,
        coinbase=tester.a0,
        key=tester.k0,
        txqueue=TransactionQueue(),
        period_start_prevhash=t1.chain.get_period_start_prevhash(expected_period_number),
    )
    assert collation_3.number == 2

    apply_add_header(
        t1,
        collation_3.header,
        privkey=tester.k0,
    )

    collations = stateless_collator.get_collations_with_scores_in_range(
        t1.head_state,
        shard_id,
        1,
        2,
    )
    assert len(collations) == 3
