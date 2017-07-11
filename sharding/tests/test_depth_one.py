import copy

from ethereum.utils import sha3, to_string, privtoaddr, int_to_addr
from ethereum.config import Env
from ethereum.slogging import get_logger
from ethereum.transaction_queue import TransactionQueue

from sharding.config import sharding_config
from sharding.tools import tester
from sharding import collator


logger = get_logger()

# Initialize accounts
accounts = []
keys = []

for account_number in range(10):
    keys.append(sha3(to_string(account_number)))
    accounts.append(privtoaddr(keys[-1]))

k0, k1, k2, k3, k4, k5, k6, k7, k8, k9 = keys[:10]
a0, a1, a2, a3, a4, a5, a6, a7, a8, a9 = accounts[:10]

base_alloc = {}
minimal_alloc = {}
for a in accounts:
    base_alloc[a] = {'balance': 10**18}
for i in range(1, 9):
    base_alloc[int_to_addr(i)] = {'balance': 1}
    minimal_alloc[int_to_addr(i)] = {'balance': 1}
minimal_alloc[accounts[0]] = {'balance': 10**18}

# Simplified configuration
sharding_config['MAX_SHARD_DEPTH'] = 1
sharding_config['SHARD_CHILD_COUNT'] = 1
sharding_config['SIGNATURE_COUNT'] = 1


def test_simple_sharding_script():
    """A simple script to test the functions of shard_chain.py and collator.py
    """
    env = Env(config=sharding_config)

    # Node 1:
    # main shard (shard 0)
    # assume a0, a1, a2 are in shard 0
    ms_signer_alloc = copy.deepcopy(base_alloc)
    ms_signer = tester.Chain(ms_signer_alloc, env, shardId=0)

    # Node 2:
    # collator of main_shard
    ms_collator_alloc = copy.deepcopy(ms_signer_alloc)
    ms_collator_env = Env(
        config=sharding_config,
        db=copy.deepcopy(ms_signer.chain.db))
    ms_collator = tester.Chain(ms_collator_alloc, ms_collator_env, shardId=0)

    # Node 3:
    # collator of child shard (shard 1)
    # assume a3, a4, a5 are in shard 1
    child_shardId = 1

    cs_collator_alloc = copy.deepcopy(ms_signer_alloc)
    cs_env = Env(
        config=sharding_config,
        db=copy.deepcopy(ms_signer.chain.db))
    cs_collator = tester.Chain(cs_collator_alloc, cs_env, shardId=child_shardId)

    # Node 4:
    # signer of child_shard
    cs_signer_alloc = copy.deepcopy(cs_collator_alloc)
    child_signer_env = Env(
        config=sharding_config,
        db=copy.deepcopy(cs_collator.chain.db))
    cs_signer = tester.Chain(cs_signer_alloc, child_signer_env, shardId=child_shardId)

    print_current_block_number(ms_signer)
    print_current_block_number(ms_collator)
    print_current_block_number(cs_collator)
    print_current_block_number(cs_signer)

    logger.info('[STEP 1] The collator of `child_shard`(shard 1) creates a collation and broadcasts it')
    # Some transactions
    tx1 = cs_collator.generate_shard_tx(tester.k3, tester.a4, 2)
    tx2 = cs_collator.generate_shard_tx(tester.k4, tester.a5, 5)
    # Prepare txqueue
    txqueue = TransactionQueue()
    txqueue.add_transaction(tx1)
    txqueue.add_transaction(tx2)

    # It's the first collation of child_shard
    prev_state = cs_collator.chain.get_shard_head_state()
    collation = collator.create_collation(
        cs_collator.chain, txqueue,
        prev_state,
        tester.a3)
    print_collation(collation)

    logger.info('[STEP 2-1] The signer of `child_shard` receives the collation and verifies it')
    # The signer validates the collation
    prev_state = cs_signer.chain.get_shard_head_state()
    is_valid = collator.verify_collation_header(
        cs_signer.chain,
        collation_header=collation.header,
        prev_state=prev_state,
        children_header=[],
        main_chain_included=False)
    assert is_valid
    is_valid = collator.verify_collation(
        cs_signer.chain,
        collation=collation,
        prev_state=prev_state,
        children_header=[])
    assert is_valid

    logger.info('[STEP 2-2] The signer of `child_shard` signs')
    signed, collation.header = collator.sign_collation_header(cs_signer.chain, collation.header, '')

    child_shard_collation = collation

    logger.info('[STEP 3] The collator of `main_shard` creates a collation and broadcasts it')
    prev_state = ms_collator.chain.get_shard_head_state()
    children_header = [child_shard_collation.header]
    collation = collator.create_collation(
        ms_collator.chain, TransactionQueue(),
        prev_state,
        tester.a3,
        children_header=children_header)
    print_collation(collation)

    logger.info('[STEP 4-1] The signer of `main_shard` verifies the collation')
    prev_state = ms_signer.chain.get_shard_head_state()
    children_header = [child_shard_collation.header]
    is_valid = collator.verify_collation_header(
        ms_signer.chain,
        collation_header=collation.header,
        prev_state=prev_state,
        children_header=children_header,
        main_chain_included=False)
    assert is_valid
    is_valid = collator.verify_collation(
        cs_signer.chain,
        collation=collation,
        prev_state=prev_state,
        children_header=children_header)
    assert is_valid

    logger.info('[STEP 4-2] The signer of `main_shard` signs collation and broadcasts it')
    signed, collation.header = collator.sign_collation_header(ms_signer.chain, collation.header, '')
    print_collation(collation)

    logger.info('[STEP 5] The miner of top-level block sets the block.header.extra_data to collation_header of shard 0 and broadcasts')
    prev_state = ms_signer.chain.get_shard_head_state()
    ms_signer.mine(1, coinbase=tester.a0, collation_header=collation.header)
    blknum = ms_signer.chain.state.block_number
    blk = ms_signer.chain.get_block_by_number(blknum)
    ms_signer.chain.add_block(blk)
    # apply_collation(ms_signer.chain, blk.header.hash, collation, children_header)
    collator.apply_collation(ms_signer.chain, prev_state, collation, blk.header.hash, children_header=children_header)

    # assert main_shard.chain.block_contains_collation_header(blk.hash)
    logger.info('[STEP 6-1] The collator of `main_shard` receives the latest block, call `add_block`and update the `parent_block` list')
    ms_collator.chain.add_block(blk)
    logger.info('[STEP 6-2] The collator of `main_shard` apply collation')
    prev_state = ms_collator.chain.get_shard_head_state()
    collator.apply_collation(ms_collator.chain, prev_state, collation, blk.header.hash, children_header=children_header)
    # apply_collation(ms_collator.chain, blk.header.hash, collation, children_header)

    logger.info('[STEP 6-3] The collator of `child_shard` receives the latest block, call `add_block`and update the `parent_block` list')
    cs_collator.chain.add_block(blk)
    logger.info('[STEP 6-4] The collator of `child_shard` apply child_shard_collation')
    prev_state = cs_collator.chain.get_shard_head_state()
    collator.apply_collation(cs_collator.chain, prev_state, child_shard_collation, blk.header.hash)

    logger.info('[STEP 6-5] The signer of `child_shard` receives the latest block, call `add_block`and update the `parent_block` list')
    cs_signer.chain.add_block(blk)
    logger.info('[STEP 6-6] The signer of `child_shard` apply child_shard_collation')
    prev_state = cs_signer.chain.get_shard_head_state()
    collator.apply_collation(cs_signer.chain, prev_state, child_shard_collation, blk.header.hash)

    logger.info('---------------------------------------------------------')
    logger.info('[STEP 7] The collator of `child_shard`(shard 1) creates a collation and broadcasts it')
    tx1 = cs_collator.generate_shard_tx(tester.k3, tester.a4, 2)
    tx2 = cs_collator.generate_shard_tx(tester.k4, tester.a5, 3)
    txqueue = TransactionQueue()
    txqueue.add_transaction(tx1)
    txqueue.add_transaction(tx2)

    # It's the second collation of child_shard
    prev_state = cs_collator.chain.get_shard_head_state()
    collation = collator.create_collation(
        cs_collator.chain,
        txqueue,
        prev_state,
        tester.a3)
    print_collation(collation)

    logger.info('[STEP 8] The signer of `child_shard` receives the collation and verifies it')
    # The signer validates the collation
    # Assume the signed received the collation
    prev_state = cs_signer.chain.get_prev_state(collation.header.parent_block_hash)
    is_valid = collator.verify_collation_header(
        cs_signer.chain,
        collation_header=collation.header,
        prev_state=prev_state,
        children_header=[],
        main_chain_included=False)
    assert is_valid
    is_valid = collator.verify_collation(
        cs_signer.chain,
        collation=collation,
        prev_state=prev_state,
        children_header=[])
    assert is_valid

    logger.info('[STEP 8] The signer of `child_shard` signs the collation')
    signed, collation.header = collator.sign_collation_header(cs_signer.chain, collation.header, '')
    print_collation(collation)
    assert signed


def print_current_block_number(shard):
    """Print the current block number of the shard chain
    """
    block_number = shard.head_state.block_number
    logger.info('block_number of shard #{}: {}'.format(
        shard.chain.shardId, block_number))


def print_collation(collation):
    collation_dict = collation.to_dict()
    logger.info('collation_dict: {}'.format(collation_dict))
    logger.info('collation.transaction_count: {}\n'.format(collation.transaction_count))
