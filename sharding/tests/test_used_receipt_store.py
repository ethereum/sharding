import pytest

from ethereum import utils
from ethereum.messages import apply_transaction

from sharding.tools import tester as t
from sharding.used_receipt_store_utils import (create_urs_tx, get_urs_ct,
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
        print(apply_transaction(c.head_state, tx))
    for tx in txs:
        print(apply_transaction(c.head_state, tx))
    return
    for tx in txs:
        c.direct_tx(tx)
    x = t.ABIContract(c, get_urs_ct(shard_id), get_urs_contract(shard_id)['addr'])
    c.mine(1)
    assert not x.get_used_receipts(0)
    x.add_used_receipt(0)
    assert x.get_used_receipts(0)
