import pytest

from ethereum import utils

from sharding.tools import tester as t
from sharding.used_receipt_store_utils import (call_add_used_receipt,
                                               call_urs,
                                               get_urs_contract,
                                               mk_initiating_txs_for_urs)


def chain(shard_id):
    t.base_alloc[get_urs_contract(shard_id)['addr']] = {
        'balance': (10 ** 9) * utils.denoms.ether
    }
    return t.Chain()


def test_used_receipt_store():
    shard_id = 0
    c = chain(shard_id)
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
