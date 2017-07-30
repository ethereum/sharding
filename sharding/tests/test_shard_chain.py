import pytest
import copy
import rlp
from ethereum.state import State
from ethereum.config import Env
from ethereum.tools import tester
from ethereum.utils import encode_hex
from ethereum.db import EphemDB

from sharding.config import sharding_config
from sharding.shard_chain import ShardChain
from sharding.collator import create_collation
# from sharding.collator import generate_state_branch_node, get_geometric_progression_sum
from sharding.state_transition import mk_collation_from_prevstate
from sharding.collation import Collation


@pytest.fixture(scope="function")
def initial_shard_chain():
    env = Env(config=sharding_config, db=EphemDB())
    return ShardChain(alloc=None, shard_chain=1, env=env)


def test_add_collation_and_get_score(initial_shard_chain):
    """Test ShardChain.get_score(Collation)
    """
    shard_chain = initial_shard_chain
    collation = create_collation(shard_chain, State(env=shard_chain.env), shard_chain.env.config['GENESIS_PREVHASH'])
    shard_chain.add_collation(collation)

    prev_collation_hash = collation.header.hash

    collation = create_collation(shard_chain, shard_chain.mk_poststate_of_collation_hash(prev_collation_hash), prev_collation_hash)
    shard_chain.add_collation(collation)

    collation_rlp = shard_chain.db.get(collation.header.hash)
    assert rlp.decode(collation_rlp, Collation).header.hash == collation.header.hash
    assert shard_chain.get_score(collation) == 2

    collation = create_collation(shard_chain, State(env=shard_chain.env),
        shard_chain.env.config['GENESIS_PREVHASH'], coinbase='\x36' * 20)
    shard_chain.add_collation(collation)
    assert shard_chain.get_score(collation) == 1


def test_get_collation(initial_shard_chain):
    """Test ShardChain.get_parent()
    """
    shard_chain = initial_shard_chain
    collation = create_collation(shard_chain, State(env=shard_chain.env), shard_chain.env.config['GENESIS_PREVHASH'])
    shard_chain.add_collation(collation)

    assert shard_chain.get_collation(collation.header.hash).header.hash == collation.header.hash


def test_get_parent(initial_shard_chain):
    """Test ShardChain.get_parent()
    """
    shard_chain = shard_chain = initial_shard_chain
    collation = create_collation(shard_chain, State(env=shard_chain.env), shard_chain.env.config['GENESIS_PREVHASH'])
    shard_chain.add_collation(collation)

    prev_collation_hash = collation.header.hash

    collation = create_collation(shard_chain, shard_chain.mk_poststate_of_collation_hash(prev_collation_hash), prev_collation_hash)
    shard_chain.add_collation(collation)

    assert shard_chain.get_parent(collation).header.hash == collation.header.parent_collation_hash
