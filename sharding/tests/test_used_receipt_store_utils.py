import pytest

from ethereum import utils

from sharding.tools import tester as t
from sharding.validator_manager_utils import call_contract_inconstantly
from sharding.used_receipt_store_utils import (call_urs,
                                               get_urs_ct,
                                               get_urs_contract)


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
    urs_addr = get_urs_contract(shard_id)['addr']
    assert call_contract_inconstantly(
        state, get_urs_ct(shard_id), urs_addr,
        'add_used_receipt', [receipt_id],
        0, sender_addr=urs_addr
    )
    assert call_urs(state, shard_id, 'get_used_receipts', [receipt_id])
