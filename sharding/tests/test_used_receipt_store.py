import pytest

from ethereum import utils
from ethereum.messages import apply_transaction

from sharding.tools import tester as t
from sharding.used_receipt_store_utils import (create_urs_tx, get_urs_ct,
                                               get_urs_contract,
                                               mk_initiating_txs_for_urs)
from sharding.validator_manager_utils import (MessageFailed,
                                             call_contract_inconstantly)

def chain(shard_id):
    c = t.Chain(env='sharding', deploy_sharding_contracts=True)
    c.mine(5)
    c.add_test_shard(shard_id)
    return c


def test_used_receipt_store():
    shard_id = 0
    c = chain(shard_id)
    shard_state = c.shard_head_state[shard_id]
    x = t.ABIContract(
        c, get_urs_ct(shard_id), get_urs_contract(shard_id)['addr'],
        shard_id=shard_id
    )
    assert not x.get_used_receipts(0)
    urs_addr = get_urs_contract(shard_id)['addr']
    # test add_used_receipt: only USED_RECEIPT_STORE can call itself with msg
    with pytest.raises(MessageFailed):
        call_contract_inconstantly(
            shard_state, get_urs_ct(shard_id), urs_addr,
            'add_used_receipt', [0],
            0, sender_addr=t.a0
        )
    assert call_contract_inconstantly(
        shard_state, get_urs_ct(shard_id), urs_addr,
        'add_used_receipt', [0],
        0, sender_addr=urs_addr
    )
    assert x.get_used_receipts(0)
