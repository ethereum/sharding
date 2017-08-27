import pytest

from ethereum import utils, vm
from ethereum.messages import VMExt, apply_message, apply_msg, apply_transaction
from ethereum.slogging import configure_logging, get_logger
from ethereum.transactions import Transaction

from sharding.tools import tester as t
from sharding.used_receipt_store_utils import call_get_used_receipts, get_urs_ct, get_urs_contract, mk_initiating_txs_for_urs
from sharding.validator_manager_utils import MessageFailed, call_msg, call_tx, get_valmgr_addr, get_valmgr_ct, mk_initiating_contracts, mk_validation_code, sign

# config_string = 'eth.chain:info,eth.pb.msg:debug'
# configure_logging(config_string=config_string)
log_rctx = get_logger('sharding.rctx')
config_string = 'sharding.rctx:debug'
configure_logging(config_string=config_string)

@pytest.fixture
def c():
    for k, v in t.base_alloc.items():
        t.base_alloc[k] = {'balance': 10 * 100 * utils.denoms.ether}
    return t.Chain(alloc=t.base_alloc)


def call_urs(state, shard_id, func, args):
    dummy_addr = '\x00' * 20
    ct = get_urs_ct(shard_id)
    result = call_msg(
        state, ct, func, args,
        dummy_addr, get_urs_contract(shard_id)['addr'], 0
    )
    o = ct.decode(func, result)
    return o[0] if len(o) == 1 else o


def call_valmgr(state, func, args):
    dummy_addr = '\x00' * 20
    ct = get_valmgr_ct()
    result = call_msg(state, ct, func, args, dummy_addr, get_valmgr_addr(), 0)
    o = ct.decode(func, result)
    return o[0] if len(o) == 1 else o


def simplified_validate_transaction(state, tx):
    '''A simplified and modified one from
       `ethereum.messages.validate_transction`
       Every check involved in tx.sender is removed.
    '''
    if state.gas_used + tx.startgas > state.gas_limit:
        return False
    # TODO: a check to prevent the tx from using too much space
    # if len(tx.data) >= 420:
    #     return False

    return True


def is_receipt_consuming_tx_valid(state, shard_id, tx):
    if (tx.v != 1) or (tx.s != 0) or not isinstance(tx.r, int):
        return False
    if not simplified_validate_transaction(state, tx):
        return False
    receipt_id = tx.r
    receipt_shard_id = call_valmgr(state, 'get_receipts__shard_id', [receipt_id])
    receipt_value = call_valmgr(state, 'get_receipts__value', [receipt_id])
    if receipt_value <= 0:
        return False
    receipt_to = call_valmgr(state, 'get_receipts__to', [receipt_id])
    if ((receipt_shard_id != shard_id) or
        (receipt_value != tx.value) or
        (receipt_to != hex(utils.big_endian_to_int((tx.to)))) or
        call_urs(state, shard_id, 'get_used_receipts', [receipt_id])):
        return False
    return True


def call_contract_inconstantly(state, ct, contract_addr, func, args, value):
    dummy_addr = b'\x00' * 20
    abidata = vm.CallData([utils.safe_ord(x) for x in ct.encode_function_call(func, args)])
    msg = vm.Message(dummy_addr, contract_addr, value, 200000, abidata)
    result = apply_message(state, msg)
    if result is None:
        raise MessageFailed("call_contract_inconstantly: failed")
    return result


def send_msg_add_receipt(state, shard_id, receipt_id):
    ct = get_urs_ct(shard_id)
    contract_addr = get_urs_contract(shard_id)['addr']
    return call_contract_inconstantly(
        state, ct, contract_addr, 'add_used_receipt', [receipt_id], 0
    )


def send_msg_transfer_value(state, shard_id, tx):
    urs_addr = get_urs_contract(shard_id)['addr']
    log_rctx.debug("Begin: urs.balance={}, tx.to.balance={}".format(state.get_balance(urs_addr), state.get_balance(tx.to)))

    receipt_id = tx.r
    to = tx.to
    # XXX: we should deduct the startgas of this message in advance, because
    #      the message may be possibly a contract, not only a normal value
    #      transfer.
    # TODO: should we deduct the intrinsic_gas of the tx, which is calculated
    #       in `apply_transaction` here?
    value = tx.value - tx.gasprice * tx.startgas
    log_rctx.debug("value={}, tx.value={}, tx.gasprice={}, tx.startgas={}".format(value, tx.value, tx.gasprice, tx.startgas))
    if value <= 0:
        return False, None

    # start transactioning
    send_msg_add_receipt(state, shard_id, receipt_id)

    receipt_sender_hex = call_valmgr(state, 'get_receipts__sender', [receipt_id])
    receipt_data = call_valmgr(state, 'get_receipts__data', [receipt_id])
    data = (b'\x00' * 12) + utils.parse_as_bin(receipt_sender_hex) + receipt_data
    msg = vm.Message(urs_addr, to, value, tx.startgas, data)
    # give money to urs_addr first, to transfer to the receipt.to
    state.delta_balance(urs_addr, value)
    # from `apply_message`
    ext = VMExt(state, Transaction(0, 0, 21000, b'', 0, b''))
    log_rctx.debug("before apply_msg: urs_addr.balance={}, tx.to.balance={}".format(state.get_balance(urs_addr), state.get_balance(tx.to)))
    # XXX: even if `transfer_value` in `apply_msg` fails, no error occurs.
    #      it seems no raise in apply_msg
    result, gas_remained, data = apply_msg(ext, msg)
    log_rctx.debug("after apply_msg:  urs_addr.balance={}, tx.to.balance={}".format(state.get_balance(urs_addr), state.get_balance(tx.to)))

    if not result:
        # TODO: is it correct to revert the balance here?
        state.delta_balance(urs_addr, -value)
        raise MessageFailed("send_msg_transfer_value: failed")

    # gas refunds goes to the `to` address
    refunds = gas_remained * tx.gasprice
    log_rctx.debug("gas_remained={}, gasprice={}".format(gas_remained, tx.gasprice))
    state.delta_balance(to, refunds)
    log_rctx.debug("End: urs.balance={}, tx.to.balance={}\n\n".format(state.get_balance(urs_addr), state.get_balance(tx.to)))

    # TODO: handle the state.gas_used, whenever result is True or False,
    #       referenced from `apply_transaction`.

    return True, (utils.bytearray_to_bytestr(data) if result else None)


def mk_testing_receipt_consuming_tx(receipt_id, to_addr, value, data=b''):
    startgas = 300000
    tx = Transaction(0, t.GASPRICE, startgas, to_addr, value, data)
    tx.v, tx.r, tx.s = 1, receipt_id, 0
    return tx


def test_receipt_consuming_transaction(c):
    shard_id = 0
    txs = mk_initiating_contracts(t.k0, c.head_state.get_nonce(t.a0))
    for tx in txs:
        c.direct_tx(tx)
    c.mine(1)
    valmgr = t.ABIContract(c, get_valmgr_ct(), get_valmgr_addr())
    to_addr = utils.privtoaddr(utils.sha3("test_to_addr"))

    data = b''

    # # test the case when the to_addr is a contract_address
    # k0_valcode_addr = c.tx(t.k0, '', 0, mk_validation_code(t.a0))
    # to_addr = k0_valcode_addr
    # msg_hash = utils.sha3("test_msg")
    # sig = sign(msg_hash, t.k0)
    # data = utils.sha3("test_msg1") + sig

    # registre receipts
    valmgr.tx_to_shard(to_addr, shard_id, b'', sender=t.k0, value=1)
    value = 500000
    receipt_id = valmgr.tx_to_shard(to_addr, shard_id, data, sender=t.k0, value=value)
    # create the contract USED_RECEIPT_STORE in shard 0
    txs = mk_initiating_txs_for_urs(t.k0, c.head_state.get_nonce(t.a0), shard_id)
    for tx in txs:
        c.direct_tx(tx)
    urs0 = t.ABIContract(c, get_urs_ct(shard_id), get_urs_contract(shard_id)['addr'])
    receipt_id = 1
    c.mine(1)
    assert not urs0.get_used_receipts(receipt_id)
    c.mine(1)

    tx = mk_testing_receipt_consuming_tx(receipt_id, to_addr, value)
    if is_receipt_consuming_tx_valid(c.head_state, shard_id, tx):
        send_msg_transfer_value(c.head_state, shard_id, tx)
        send_msg_transfer_value(c.chain.state, shard_id, tx)
    c.mine(1)

    assert urs0.get_used_receipts(receipt_id)
