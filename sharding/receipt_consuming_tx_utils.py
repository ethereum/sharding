import pytest

from ethereum import opcodes, utils, vm
from ethereum.messages import CREATE_CONTRACT_ADDRESS, VMExt, apply_message, apply_msg, apply_transaction
from ethereum.slogging import get_logger
from ethereum.transactions import Transaction

from sharding.tools import tester as t
from sharding.used_receipt_store_utils import call_urs, get_urs_ct, get_urs_contract
from sharding.validator_manager_utils import MessageFailed, call_contract_inconstantly, call_valmgr

log_rctx = get_logger('sharding.rctx')

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


def is_valid_receipt_consuming_tx(mainchain_state, shard_state, shard_id, tx):
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
    # we should deduct the startgas of this message in advance, because
    # the message may be possibly a contract, not only a normal value transfer.
    value = tx.value - tx.gasprice * tx.startgas
    log_rctx.debug("value={}, tx.value={}, tx.gasprice={}, tx.startgas={}".format(value, tx.value, tx.gasprice, tx.startgas))
    if value <= 0:
        return False, None
    # calculate the intrinsic_gas
    intrinsic_gas = tx.intrinsic_gas_used
    # if mainchain_state.is_HOMESTEAD():
    #     if not tx.to or tx.to == CREATE_CONTRACT_ADDRESS:
    #         intrinsic_gas += opcodes.CREATE[3]
    #         if tx.startgas < intrinsic_gas:
    #             return False, None

    # start transactioning
    send_msg_add_receipt(shard_state, shard_id, receipt_id)

    receipt_sender_hex = call_valmgr(mainchain_state, 'get_receipts__sender', [receipt_id])
    receipt_data = call_valmgr(mainchain_state, 'get_receipts__data', [receipt_id])
    data = (b'\x00' * 12) + utils.parse_as_bin(receipt_sender_hex) + receipt_data
    msg = vm.Message(urs_addr, to, value, tx.startgas - intrinsic_gas, data)
    # from `apply_message`
    env_tx = Transaction(0, tx.gasprice, tx.startgas, b'', 0, b'')
    env_tx._sender = utils.parse_as_bin(receipt_sender_hex)
    ext = VMExt(shard_state, env_tx)
    log_rctx.debug("before apply_msg: urs_addr.balance={}, tx.to.balance={}".format(shard_state.get_balance(urs_addr), shard_state.get_balance(tx.to)))
    # XXX: even if `transfer_value` in `apply_msg` fails, no error occurs.
    #      it seems no raise in apply_msg
    result, gas_remained, data = apply_msg(ext, msg)
    log_rctx.debug("after apply_msg:  urs_addr.balance={}, tx.to.balance={}".format(shard_state.get_balance(urs_addr), shard_state.get_balance(tx.to)))

    assert gas_remained >= 0

    # gas refunds goes to the `to` address
    refunds = gas_remained * tx.gasprice
    log_rctx.debug("gas_remained={}, gasprice={}".format(gas_remained, tx.gasprice))
    shard_state.delta_balance(to, refunds)
    log_rctx.debug("End: urs.balance={}, tx.to.balance={}\n\n".format(shard_state.get_balance(urs_addr), shard_state.get_balance(tx.to)))

    # TODO: handle the state.gas_used, whenever result is True or False,
    #       referenced from `apply_transaction`.

    return True, (utils.bytearray_to_bytestr(data) if result else None)


def apply_shard_transaction(mainchain_state, shard_state, shard_id, tx):
    """Apply shard transactions, including both receipt-consuming and normal
    transactions.
    """
    if is_valid_receipt_consuming_tx(mainchain_state, shard_state, shard_id, tx):
        success, output = send_msg_transfer_value(
            mainchain_state, shard_state, shard_id, tx
        )
    else:
        success, output = apply_transaction(shard_state, tx)
    return success, output
