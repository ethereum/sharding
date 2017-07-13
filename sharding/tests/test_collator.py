from ethereum.state import State
from ethereum.config import Env

from sharding.config import sharding_config
from sharding.collator import generate_state_branch_node, get_geometric_progression_sum
from sharding.state_transition import mk_collation_from_prevstate
from sharding.tools import tester

# create_collation
env = Env(config=sharding_config)
main_shard = tester.Chain(alloc=None, env=env, shardId=0)
collation = mk_collation_from_prevstate(main_shard.chain, State())


def test_generate_state_branch_node():
    children_header = [collation.header, collation.header, collation.header]
    state_branch_node = generate_state_branch_node(children_header, State())
    assert state_branch_node is not None


def test_get_geometric_progression_sum():
    assert get_geometric_progression_sum(1, 3, 4) == 121
    assert get_geometric_progression_sum(1, 1, 1) == 1
