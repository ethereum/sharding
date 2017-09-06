import pytest

from ethereum import utils

from sharding.tools import tester as t
from sharding.used_receipt_store_utils import (call_add_used_receipt,
                                               call_urs,
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
    state = c.shard_head_state[shard_id]
    receipt_id = 1
    assert not call_urs(state, shard_id, 'get_used_receipts', [receipt_id])
    tx = call_add_used_receipt(state, t.k0, 0, shard_id, receipt_id)
    c.direct_tx(tx, shard_id=shard_id)
    assert call_urs(state, shard_id, 'get_used_receipts', [receipt_id])

