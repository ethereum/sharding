import pytest

from ethereum import utils

from sharding.tools import tester as t
from sharding.used_receipt_store_utils import (call_add_used_receipt,
                                               call_urs,
                                               mk_initiating_txs_for_urs)

@pytest.fixture
def c():
    for k, v in t.base_alloc.items():
        t.base_alloc[k] = {'balance': 10 * 100 * utils.denoms.ether}
    return t.Chain(alloc=t.base_alloc)


def test_used_receipt_store(c):
    shard_id = 0
    txs = mk_initiating_txs_for_urs(t.k0, c.head_state.get_nonce(t.a0), shard_id)
    for tx in txs:
        c.direct_tx(tx)
    c.mine(1)
    receipt_id = 1
    assert not call_urs(c.head_state, shard_id, 'get_used_receipts', [receipt_id])
    tx = call_add_used_receipt(c.head_state, t.k0, 0, shard_id, receipt_id)
    c.direct_tx(tx)
    c.mine(1)
    assert call_urs(c.head_state, shard_id, 'get_used_receipts', [receipt_id])
