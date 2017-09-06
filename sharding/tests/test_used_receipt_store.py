import pytest

from ethereum import utils
from ethereum.messages import apply_transaction

from sharding.tools import tester as t
from sharding.used_receipt_store_utils import (create_urs_tx, get_urs_ct,
                                               get_urs_contract,
                                               mk_initiating_txs_for_urs)

def chain(shard_id):
    c = t.Chain(env='sharding', deploy_sharding_contracts=True)
    c.mine(5)
    c.add_test_shard(shard_id)
    return c


def test_used_receipt_store():
    shard_id = 0
    c = chain(shard_id)
    x = t.ABIContract(
        c, get_urs_ct(shard_id), get_urs_contract(shard_id)['addr'],
        shard_id=shard_id
    )
    c.mine(1)
    assert not x.get_used_receipts(0)
    x.add_used_receipt(0)
    assert x.get_used_receipts(0)
