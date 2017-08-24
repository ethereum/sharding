import pytest

from ethereum import utils, vm
from ethereum.messages import apply_message, apply_transaction
from ethereum.slogging import configure_logging
from ethereum.transactions import Transaction

from sharding.tools import tester as t
from sharding.used_receipt_store_utils import call_get_used_receipts, get_urs_ct, get_urs_contract
from sharding.validator_manager_utils import MessageFailed, call_msg, get_valmgr_addr, get_valmgr_ct, mk_initiating_contracts

config_string = 'eth.chain:info'
configure_logging(config_string=config_string)

@pytest.fixture
def c():
    for k, v in t.base_alloc.items():
        t.base_alloc[k] = {'balance': 10 * 100 * utils.denoms.ether}
    return t.Chain(alloc=t.base_alloc)


def receipt_exists(state, receipt_id):
    dummy_addr = '\x00' * 20
    return bool(utils.big_endian_to_int(call_msg(
        state, get_valmgr_ct(),
        'get_receipts__value', [receipt_id],
        dummy_addr, get_valmgr_addr(), 0
    )))

def is_receipt_consuming_tx(state, tx):
    if (tx.v != 1) or (tx.s != 0) or not isinstance(tx.r, int):
        return False
    receipt_id = tx.r
    return receipt_exists(state, receipt_id)


def verify_receipt_consuming_tx(state, tx):
    return True


def send_msg_add_receipt(state, shard_id, receipt_id):
    ct = get_urs_ct(shard_id)
    dummy_addr = b'\x00' * 20
    abidata = vm.CallData([utils.safe_ord(x) for x in ct.encode_function_call('add_used_receipt', [receipt_id])])
    msg = vm.Message(dummy_addr, get_urs_contract(shard_id)['addr'], 0, 200000, abidata)
    result = apply_message(state, msg)
    if result is None:
        raise MessageFailed("send_msg_add_receipt: failed")
    return result


def send_msg_send_money(state, tx):
    pass


def mk_testing_receipt_consuming_tx(receipt_id, to_addr, value, data=b''):
    tx = Transaction(0, t.GASPRICE, t.STARTGAS, to_addr, value, data)
    tx.v, tx.r, tx.s = 1, receipt_id, 0
    return tx


def test_receipt_consuming_transaction(c):
    shard_id = 0
    txs = mk_initiating_contracts(t.k0, c.head_state.get_nonce(t.a0))
    for tx in txs:
        c.direct_tx(tx)
    c.mine(1)
    valmgr = t.ABIContract(c, get_valmgr_ct(), get_valmgr_addr())
    to_addr = t.a9
    # registre receipts
    valmgr.tx_to_shard(to_addr, shard_id, b'', sender=t.k0, value=1)
    value = 2
    receipt_id = valmgr.tx_to_shard(to_addr, shard_id, b'', sender=t.k0, value=value)
    # create the contract USED_RECEIPT_STORE in shard 0
    c.direct_tx(get_urs_contract(shard_id)['tx'])
    urs0 = t.ABIContract(c, get_urs_ct(shard_id), get_urs_contract(shard_id)['addr'])
    receipt_id = 1
    c.mine(1)
    assert not urs0.get_used_receipts(receipt_id)
    c.mine(1)
    send_msg_add_receipt(c.head_state, shard_id, receipt_id)
    send_msg_add_receipt(c.chain.state, shard_id, receipt_id)
    # urs0.add_used_receipt(receipt_id)
    assert urs0.get_used_receipts(receipt_id)
    c.mine(1)
    tx = mk_testing_receipt_consuming_tx(receipt_id, to_addr, value)
    print(is_receipt_consuming_tx(c.head_state, tx))
