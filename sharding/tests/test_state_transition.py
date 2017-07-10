from ethereum.state import State
from ethereum.config import Env
from ethereum.transaction_queue import TransactionQueue

from sharding.config import sharding_config
from sharding.state_transition import mk_collation_from_prevstate, add_transactions
from sharding.tools import tester

# create_collation
env = Env(config=sharding_config)
main_shard = tester.Chain(alloc=None, env=env, shardId=0)
collation = mk_collation_from_prevstate(main_shard.chain, State())


def test_mk_collation_from_prevstate():
    collation = mk_collation_from_prevstate(main_shard.chain, State())
    assert collation.hash is not None
    assert collation.header.shardId == 0


def test_add_transactions():
    main_shard.tx(tester.k1, tester.a1, 1)
    main_shard.tx(tester.k1, tester.a2, 1)

    # Prepare txqueue
    txqueue = TransactionQueue()
    for tx in main_shard.block.transactions:
        txqueue.add_transaction(tx)

    add_transactions(main_shard.chain.state, collation, txqueue, min_gasprice=0)
    assert collation.transaction_count == 2
