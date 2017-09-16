import pytest

from ethereum import opcodes, utils, vm
from ethereum.messages import CREATE_CONTRACT_ADDRESS, SKIP_MEDSTATES, VMExt, apply_msg, apply_transaction, mk_receipt
from ethereum.slogging import get_logger
from ethereum.transactions import Transaction

from sharding.used_receipt_store_utils import call_urs, get_urs_ct, get_urs_contract
from sharding.validator_manager_utils import call_contract_inconstantly, call_valmgr

log_rctx = get_logger('sharding.rctx')

def simplified_validate_transaction(state, tx):
    '''A simplified and modified one from
       `ethereum.messages.validate_transction`
       Every check involved in tx.sender is removed.
    '''
    if state.gas_used + tx.startgas > state.gas_limit:
        return False
    # TODO: limit the data size to zero. Still need to confirm the limit of
    #       `tx.data` size
    if len(tx.data) != 0:
        return False

    return True


def is_valid_receipt_consuming_tx(mainchain_state, shard_state, shard_id, tx):
    if (tx.v != 1) or (tx.s != 0) or not isinstance(tx.r, int):
        return False
    if not tx.to or tx.to == CREATE_CONTRACT_ADDRESS:
        return False
    if not simplified_validate_transaction(shard_state, tx):
        return False
    receipt_id = tx.r
    receipt_shard_id = call_valmgr(mainchain_state, 'get_receipts__shard_id', [receipt_id])
    receipt_startgas = call_valmgr(mainchain_state, 'get_receipts__tx_startgas', [receipt_id])
    receipt_gasprice = call_valmgr(mainchain_state, 'get_receipts__tx_gasprice', [receipt_id])
    receipt_value = call_valmgr(mainchain_state, 'get_receipts__value', [receipt_id])
    if receipt_value <= 0:
        return False
    receipt_to = call_valmgr(mainchain_state, 'get_receipts__to', [receipt_id])
    if ((receipt_shard_id != shard_id) or
        (receipt_startgas != tx.startgas) or
        (receipt_gasprice != tx.gasprice) or
        (receipt_value != tx.value) or
        (receipt_to != hex(utils.big_endian_to_int((tx.to)))) or
        call_urs(shard_state, shard_id, 'get_used_receipts', [receipt_id])):
        return False
    return True


def send_msg_add_used_receipt(state, shard_id, receipt_id):
    ct = get_urs_ct(shard_id)
    urs_addr = get_urs_contract(shard_id)['addr']
    return call_contract_inconstantly(
        state, ct, urs_addr, 'add_used_receipt', [receipt_id],
        0, sender_addr=urs_addr
    )


def send_msg_transfer_value(mainchain_state, shard_state, shard_id, tx):
    urs_addr = get_urs_contract(shard_id)['addr']
    log_rctx.debug("Begin: urs.balance={}, tx.to.balance={}".format(shard_state.get_balance(urs_addr), shard_state.get_balance(tx.to)))

    receipt_id = tx.r
    # we should deduct the startgas of this message in advance, because
    # the message may be possibly a contract, not only a normal value transfer.
    value = tx.value - tx.gasprice * tx.startgas
    log_rctx.debug("value={}, tx.value={}, tx.gasprice={}, tx.startgas={}".format(value, tx.value, tx.gasprice, tx.startgas))
    if value <= 0:
        return False, None

    # start transactioning
    if not send_msg_add_used_receipt(shard_state, shard_id, receipt_id):
        return False, None

    receipt_sender_hex = call_valmgr(mainchain_state, 'get_receipts__sender', [receipt_id])
    receipt_data = call_valmgr(mainchain_state, 'get_receipts__data', [receipt_id])
    msg_data = (b'00' * 12) + utils.parse_as_bin(receipt_sender_hex) + receipt_data
    msg = vm.Message(urs_addr, tx.to, value, tx.startgas - tx.intrinsic_gas_used, msg_data)
    env_tx = Transaction(0, tx.gasprice, tx.startgas, b'', 0, b'')
    env_tx._sender = urs_addr
    ext = VMExt(shard_state, env_tx)
    log_rctx.debug("before apply_msg: urs_addr.balance={}, tx.to.balance={}".format(shard_state.get_balance(urs_addr), shard_state.get_balance(tx.to)))
    # even if `transfer_value` in `apply_msg` fails, no error occurs.
    # it seems no raise in apply_msg
    result, gas_remained, data = apply_msg(ext, msg)
    log_rctx.debug("after apply_msg:  urs_addr.balance={}, tx.to.balance={}".format(shard_state.get_balance(urs_addr), shard_state.get_balance(tx.to)))

    assert gas_remained >= 0

    gas_used = tx.startgas - gas_remained

    # Transaction failed
    if not result:
        log_rctx.debug('TX FAILED', reason='out of gas',
                       startgas=tx.startgas, gas_remained=gas_remained)
        shard_state.gas_used += tx.startgas
        shard_state.delta_balance(tx.to, tx.gasprice * gas_remained)
        shard_state.delta_balance(shard_state.block_coinbase, tx.gasprice * gas_used)
        output = b''
        success = 0
    # Transaction success
    else:
        log_rctx.debug('TX SUCCESS', data=data)
        shard_state.refunds += len(set(shard_state.suicides)) * opcodes.GSUICIDEREFUND
        if shard_state.refunds > 0:
            log_rctx.debug('Refunding', gas_refunded=min(shard_state.refunds, gas_used // 2))
            gas_remained += min(shard_state.refunds, gas_used // 2)
            gas_used -= min(shard_state.refunds, gas_used // 2)
            shard_state.refunds = 0
        # sell remaining gas
        shard_state.delta_balance(tx.to, tx.gasprice * gas_remained)
        log_rctx.debug("gas_remained={}, gasprice={}".format(gas_remained, tx.gasprice))
        log_rctx.debug("End: urs.balance={}, tx.to.balance={}".format(shard_state.get_balance(urs_addr), shard_state.get_balance(tx.to)))
        shard_state.delta_balance(shard_state.block_coinbase, tx.gasprice * gas_used)
        shard_state.gas_used += gas_used
        if tx.to:
            output = utils.bytearray_to_bytestr(data)
        else:
            output = data
        success = 1

    # Clear suicides
    suicides = shard_state.suicides
    shard_state.suicides = []
    for s in suicides:
        shard_state.set_balance(s, 0)
        shard_state.del_account(s)

    # Pre-Metropolis: commit state after every tx
    if not shard_state.is_METROPOLIS() and not SKIP_MEDSTATES:
        shard_state.commit()

    # Construct a receipt
    r = mk_receipt(shard_state, success, shard_state.logs)
    _logs = list(shard_state.logs)
    shard_state.logs = []
    shard_state.add_receipt(r)
    shard_state.set_param('bloom', shard_state.bloom | r.bloom)
    shard_state.set_param('txindex', shard_state.txindex + 1)

    return success, output


def apply_shard_transaction(mainchain_state, shard_state, shard_id, tx):
    """Apply shard transactions, including both receipt-consuming and normal
    transactions.
    """
    if ((mainchain_state is not None) and (shard_id is not None) and
            is_valid_receipt_consuming_tx(mainchain_state, shard_state, shard_id, tx)):
        success, output = send_msg_transfer_value(
            mainchain_state, shard_state, shard_id, tx
        )
    else:
        success, output = apply_transaction(shard_state, tx)
    return success, output
