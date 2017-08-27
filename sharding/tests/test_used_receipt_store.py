import pytest

from ethereum import utils

from sharding.tools import tester as t
from sharding.used_receipt_store_utils import (create_urs_tx, get_urs_ct,
                                               get_urs_contract,
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
    x = t.ABIContract(c, get_urs_ct(shard_id), get_urs_contract(shard_id)['addr'])
    c.mine(1)
    assert not x.get_used_receipts(0)
    x.add_used_receipt(0)
    assert x.get_used_receipts(0)
