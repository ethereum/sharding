import pytest

from ethereum import utils, vm
from ethereum.messages import VMExt, apply_message, apply_msg, apply_transaction
from ethereum.slogging import get_logger
from ethereum.transactions import Transaction

from sharding.tools import tester as t
from sharding.used_receipt_store_utils import call_get_used_receipts, get_urs_ct, get_urs_contract, mk_initiating_txs_for_urs
from sharding.validator_manager_utils import MessageFailed, call_contract_constantly, call_contract_inconstantly, call_tx, get_valmgr_addr, get_valmgr_ct, mk_initiating_contracts, mk_validation_code, sign

log_rctx = get_logger('sharding.rctx')

def call_urs(state, shard_id, func, args):
    ct = get_urs_ct(shard_id)
    return call_contract_constantly(
        state, ct, get_urs_contract(shard_id)['addr'],
        func, args, 0
    )


def call_valmgr(state, func, args):
    ct = get_valmgr_ct()
    return call_contract_constantly(
        state, ct, get_valmgr_addr(),
        func, args, 0
    )

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


def is_receipt_consuming_tx_valid(mainchain_state, shard_state, shard_id, tx):
    if (tx.v != 1) or (tx.s != 0) or not isinstance(tx.r, int):
        return False
    if not simplified_validate_transaction(shard_state, tx):
        return False
    receipt_id = tx.r
    receipt_shard_id = call_valmgr(mainchain_state, 'get_receipts__shard_id', [receipt_id])
    receipt_value = call_valmgr(mainchain_state, 'get_receipts__value', [receipt_id])
    if receipt_value <= 0:
        return False
    receipt_to = call_valmgr(mainchain_state, 'get_receipts__to', [receipt_id])
    if ((receipt_shard_id != shard_id) or
        (receipt_value != tx.value) or
        (receipt_to != hex(utils.big_endian_to_int((tx.to)))) or
        call_urs(shard_state, shard_id, 'get_used_receipts', [receipt_id])):
        return False
    return True


def send_msg_add_receipt(state, shard_id, receipt_id):
    ct = get_urs_ct(shard_id)
    contract_addr = get_urs_contract(shard_id)['addr']
    return call_contract_inconstantly(
        state, ct, contract_addr, 'add_used_receipt', [receipt_id], 0
    )


def send_msg_transfer_value(mainchain_state, shard_state, shard_id, tx):
    urs_addr = get_urs_contract(shard_id)['addr']
    log_rctx.debug("Begin: urs.balance={}, tx.to.balance={}".format(shard_state.get_balance(urs_addr), shard_state.get_balance(tx.to)))

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
    send_msg_add_receipt(shard_state, shard_id, receipt_id)

    receipt_sender_hex = call_valmgr(mainchain_state, 'get_receipts__sender', [receipt_id])
    receipt_data = call_valmgr(mainchain_state, 'get_receipts__data', [receipt_id])
    data = (b'\x00' * 12) + utils.parse_as_bin(receipt_sender_hex) + receipt_data
    msg = vm.Message(urs_addr, to, value, tx.startgas, data)
    # give money to urs_addr first, to transfer to the receipt.to
    shard_state.delta_balance(urs_addr, value)
    # from `apply_message`
    ext = VMExt(shard_state, Transaction(0, 0, 21000, b'', 0, b''))
    log_rctx.debug("before apply_msg: urs_addr.balance={}, tx.to.balance={}".format(shard_state.get_balance(urs_addr), shard_state.get_balance(tx.to)))
    # XXX: even if `transfer_value` in `apply_msg` fails, no error occurs.
    #      it seems no raise in apply_msg
    result, gas_remained, data = apply_msg(ext, msg)
    log_rctx.debug("after apply_msg:  urs_addr.balance={}, tx.to.balance={}".format(shard_state.get_balance(urs_addr), shard_state.get_balance(tx.to)))

    if not result:
        # TODO: is it correct to revert the balance here?
        shard_state.delta_balance(urs_addr, -value)
        raise MessageFailed("send_msg_transfer_value: failed")

    # gas refunds goes to the `to` address
    refunds = gas_remained * tx.gasprice
    log_rctx.debug("gas_remained={}, gasprice={}".format(gas_remained, tx.gasprice))
    shard_state.delta_balance(to, refunds)
    log_rctx.debug("End: urs.balance={}, tx.to.balance={}\n\n".format(shard_state.get_balance(urs_addr), shard_state.get_balance(tx.to)))

    # TODO: handle the state.gas_used, whenever result is True or False,
    #       referenced from `apply_transaction`.

    return True, (utils.bytearray_to_bytestr(data) if result else None)
