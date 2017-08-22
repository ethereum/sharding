import pytest

from ethereum import utils, vm
from ethereum.messages import apply_message, apply_transaction
from ethereum.slogging import configure_logging

from sharding.tools import tester as t
from sharding.used_receipt_store_utils import call_get_used_receipts, get_urs_ct, get_urs_contract
from sharding.validator_manager_utils import MessageFailed, get_valmgr_addr, get_valmgr_ct, mk_initiating_contracts

config_string = 'eth.chain:info'
configure_logging(config_string=config_string)

@pytest.fixture
def c():
    for k, v in t.base_alloc.items():
        t.base_alloc[k] = {'balance': 10 * 100 * utils.denoms.ether}
    return t.Chain(alloc=t.base_alloc)


def send_msg_add_receipt(state, shard_id, receipt_id):
    ct = get_urs_ct(shard_id)
    dummy_addr = b'\x00' * 20
    abidata = vm.CallData([utils.safe_ord(x) for x in ct.encode_function_call('add_used_receipt', [receipt_id])])
    msg = vm.Message(dummy_addr, get_urs_contract(shard_id)['addr'], 0, 200000, abidata)
    result = apply_message(state, msg)
    if result is None:
        raise MessageFailed("send_msg_add_receipt: failed")
    return result


def test_receipt_consuming_transaction(c):
    shard_id = 0
    txs = mk_initiating_contracts(t.k0, c.head_state.get_nonce(t.a0))
    for tx in txs:
        c.direct_tx(tx)
    c.mine(1)
    valmgr = t.ABIContract(c, get_valmgr_ct(), get_valmgr_addr())
    c.direct_tx(get_urs_contract(shard_id)['tx'])
    urs0 = t.ABIContract(c, get_urs_ct(shard_id), get_urs_contract(shard_id)['addr'])
    shard_id = 0
    receipt_id = 1
    c.mine(1)
    assert not urs0.get_used_receipts(receipt_id)
    send_msg_add_receipt(c.head_state, shard_id, receipt_id)
    c.mine(1)
    # urs0.add_used_receipt(receipt_id)
    # rint(call_get_used_receipts(c.head_state, shard_id, receipt_id))
    assert urs0.get_used_receipts(receipt_id)

