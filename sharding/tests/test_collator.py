import pytest
import logging

from ethereum.slogging import get_logger
from ethereum.transaction_queue import TransactionQueue
from ethereum import utils
from ethereum import trie
from ethereum.exceptions import VerificationFailed
from ethereum.state import State

from sharding import collator
from sharding.collation import Collation, CollationHeader
from sharding.tools import tester
from sharding.config import sharding_config

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
        c.mine(sharding_config['SHUFFLING_CYCLE_LENGTH'])
    c.add_test_shard(shard_id)
    return c


def test_create_collation_empty_txqueue():
    """Test create_collation without transactions
    """
    shard_id = 1
    t = chain(shard_id)

    parent_collation_hash = t.chain.shards[shard_id].head_hash
    expected_period_number = t.chain.get_expected_period_number()

    txqueue = TransactionQueue()
    collation = collator.create_collation(
        t.chain,
        shard_id,
        parent_collation_hash,
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
            parent_collation_hash,
            expected_period_number,
            coinbase=tester.a1,
            key=123,
            txqueue=txqueue)


def test_create_collation_with_txs():
    """Test create_collation with transactions
    """
    shard_id = 1
    t = chain(shard_id)

    parent_collation_hash = t.chain.shards[shard_id].head_hash
    expected_period_number = t.chain.get_expected_period_number()

    txqueue = TransactionQueue()
    tx1 = t.generate_shard_tx(shard_id, tester.k2, tester.a4, int(0.03 * utils.denoms.ether))
    tx2 = t.generate_shard_tx(shard_id, tester.k3, tester.a5, int(0.03 * utils.denoms.ether))
    txqueue.add_transaction(tx1)
    txqueue.add_transaction(tx2)

    collation = collator.create_collation(
        t.chain,
        shard_id,
        parent_collation_hash,
        expected_period_number,
        coinbase=tester.a0,
        key=tester.k0,
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

    collator.apply_collation(state, collation, period_start_prevblock, t.chain.state)

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
        collator.apply_collation(state, collation, period_start_prevblock, t.chain.state)

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
        collator.apply_collation(state, collation, period_start_prevblock, t.chain.state)

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
        collator.apply_collation(state, collation, period_start_prevblock, t.chain.state)


def test_verify_collation_header():
    shard_id = 1
    t = chain(shard_id)

    parent_collation_hash = t.chain.shards[shard_id].head_hash
    expected_period_number = t.chain.get_expected_period_number()

    txqueue = TransactionQueue()
    tx1 = t.generate_shard_tx(shard_id, tester.k2, tester.a4, int(0.03 * utils.denoms.ether))
    tx2 = t.generate_shard_tx(shard_id, tester.k3, tester.a5, int(0.03 * utils.denoms.ether))
    txqueue.add_transaction(tx1)
    txqueue.add_transaction(tx2)

    collation = collator.create_collation(
        t.chain,
        shard_id,
        parent_collation_hash,
        expected_period_number,
        coinbase=tester.a0,
        key=tester.k0,
        txqueue=txqueue)

    # Verify collation header
    assert collator.verify_collation_header(t.chain, collation.header)

    # Bad collation header 1
    collation = collator.create_collation(
        t.chain,
        shard_id,
        parent_collation_hash,
        expected_period_number,
        coinbase=tester.a1,
        key=tester.k1,
        txqueue=txqueue)
    collation.header.shard_id = -1
    with pytest.raises(ValueError):
        collator.verify_collation_header(t.chain, collation.header)

    # Bad collation header 2 - call_msg_add_header error
    collation = collator.create_collation(
        t.chain,
        shard_id,
        parent_collation_hash,
        expected_period_number,
        coinbase=tester.a1,
        key=tester.k1,
        txqueue=txqueue)
    collation.header.sig = utils.sha3('hello')
    with pytest.raises(ValueError):
        collator.verify_collation_header(t.chain, collation.header)


def test_get_deep_collation_hash_and_mk_fast_sync_state():
    shard_id = 1
    t = chain(shard_id)

    collhash_map = []
    for i in range(6):
        collate_one(t, shard_id)
        collhash_map.append(t.chain.shards[shard_id].head.hash)
        # Set the pivot point
        if i == 4:
            temp_state_root = t.chain.shards[shard_id].state.trie.root_hash
            temp_a0_balance = t.chain.shards[shard_id].state.get_balance(tester.a0)
            t.tx(shard_id=shard_id, sender=tester.k0, value=100)

    assert t.chain.shards[shard_id].head.number == 6

    assert collator.get_deep_collation_hash(t.chain, shard_id, 1) == collhash_map[4]
    assert collator.get_deep_collation_hash(t.chain, shard_id, 5) == collhash_map[0]
    assert collator.get_deep_collation_hash(t.chain, shard_id, 6) == collhash_map[0]

    state = collator.mk_fast_sync_state(t.chain, shard_id, collhash_map[4])
    assert state.trie.root_hash != t.chain.shards[shard_id].state.trie.root_hash
    assert state.trie.root_hash == temp_state_root
    assert t.chain.shards[shard_id].state.get_balance(tester.a0) != temp_a0_balance
    assert state.get_balance(tester.a0) == temp_a0_balance


def collate_one(testchain, shard_id):
    expected_period_number = testchain.chain.get_expected_period_number()
    testchain.set_collation(shard_id, expected_period_number)
    testchain.collate(shard_id, tester.k0)
    testchain.mine(5)


def test_verify_fast_sync_data():
    # t1: Sender
    shard_id = 1
    t1 = chain(shard_id)
    collate_one(t1, shard_id)

    received_collation = t1.chain.shards[shard_id].head
    received_state_snapshot = t1.chain.shards[shard_id].state.to_snapshot()
    received_state = State.from_snapshot(received_state_snapshot, t1.chain.env, executing_on_head=True)

    for _ in range(5):
        collate_one(t1, shard_id)

    # t2: Receiver
    t2 = chain(shard_id)
    for _ in range(6):
        collate_one(t2, shard_id)

    assert t2.head_state.trie.root_hash == t1.head_state.trie.root_hash
    assert received_collation.post_state_root == received_state.trie.root_hash

    # Set that t2 doesn't have shard 1 data
    del(t2.chain.shards[shard_id])
    t2.chain.shard_id_list.remove(shard_id)

    success = collator.verify_fast_sync_data(
        t2.chain,
        shard_id,
        received_state,
        received_collation,
        depth=5,
    )

    assert success

    # if shard_state.trie.root_hash != received_collation.post_state_root
    with pytest.raises(VerificationFailed):
        success = collator.verify_fast_sync_data(
            t2.chain,
            shard_id,
            State(),
            received_collation,
            depth=5,
        )

    # if received_collation_score <= 0
    with pytest.raises(VerificationFailed):
        success = collator.verify_fast_sync_data(
            t2.chain,
            shard_id,
            received_state,
            Collation(CollationHeader()),
            depth=5,
        )

    # if head_collation_score > received_collation_score + depth:
    with pytest.raises(VerificationFailed):
        success = collator.verify_fast_sync_data(
            t2.chain,
            shard_id,
            received_state,
            received_collation,
            depth=1,
        )
