import os

from ethereum.tools import tester as t
from ethereum import abi, utils, vm
from ethereum.messages import apply_transaction, apply_message
from ethereum.transactions import Transaction
import serpent
import viper

#from sharding.tools import tester

STARTGAS = 10 ** 8
GASPRICE = 0

_valmgr_ct = None
_valmgr_code = None
_valmgr_addr = None


class MessageFailed(Exception):

    pass


class TransactionFailed(Exception):

    pass


def mk_validation_code(address):
    validation_code = """
~calldatacopy(0, 0, 128)
~call(3000, 1, 0, 0, 128, 0, 32)
return(~mload(0) == {})
    """.format(utils.checksum_encode(address))
    return validation_code


def get_valmgr_code():
    global _valmgr_code
    if not _valmgr_code:
        mydir = os.path.dirname(__file__)
        valmgr_path = os.path.join(mydir, 'contracts/validator_manager.v.py')
        _valmgr_code = open(valmgr_path).read()
    return _valmgr_code


def get_valmgr_ct():
    global _valmgr_ct, _valmgr_code
    if not _valmgr_ct:
        _valmgr_ct = abi.ContractTranslator(
            viper.compiler.mk_full_signature(get_valmgr_code())
        )
    return _valmgr_ct


def deploy_contract(state, sender_privkey, bytecode):
    tx = Transaction(
            state.get_nonce(utils.privtoaddr(sender_privkey)),
            GASPRICE, STARTGAS, to=b'', value=0,
            data=bytecode
    ).sign(sender_privkey)
    success, output = apply_transaction(state, tx)
    if not success:
        raise TransactionFailed("Failed to deploy the contract")
    return output # addr


def deploy_valmgr_contract(state, sender_privkey):
    global _valmgr_addr
    # FIXME: should valmgr contract only exist once?
    if _valmgr_addr is not None:
        return _valmgr_addr
    try:
        return deploy_contract(
            state,
            sender_privkey,
            viper.compiler.compile(get_valmgr_code())
        )
    except TransactionFailed:
        raise TransactionFailed("Failed to deploy the validator manager")


def call_msg(state, ct, func, args, sender_addr, to, value=0, startgas=STARTGAS):
    abidata = vm.CallData([utils.safe_ord(x) for x in ct.encode_function_call(func, args)])
    msg = vm.Message(sender_addr, to, value, startgas, abidata)
    result = apply_message(state, msg)
    if not result:
        raise MessageFailed("Msg failed")
    return result


def call_tx(state, ct, func, args, sender, to, value=0, startgas=STARTGAS, gasprice=GASPRICE):
    # Transaction(nonce, gasprice, startgas, to, value, data, v=0, r=0, s=0)
    tx = Transaction(state.get_nonce(utils.privtoaddr(sender)), gasprice, startgas, to, value,
            ct.encode_function_call(func, args)
         )
    tx = tx.sign(sender)
    # refer to the tester.tx
    success, output = apply_transaction(state, tx)
    # TODO: still need to return the tx to broadcast it
    if not success:
        raise TransactionFailed("Tx failed")
    return output, tx


def call_deposit(state, validator_manager_addr, sender_privkey, value, validation_code_addr, return_addr):
    ct = get_valmgr_ct()
    result, tx = call_tx(
        state, ct, 'deposit', [validation_code_addr, return_addr],
        sender_privkey, validator_manager_addr, value
    )
    return utils.big_endian_to_int(result), tx


def call_withdraw(state, validator_manager_addr, sender_privkey, validator_index, signature):
    ct = get_valmgr_ct()
    result, tx = call_tx(
        state, ct, 'withdraw', [validator_index, signature],
        sender_privkey, validator_manager_addr, 0
    )
    return bool(utils.big_endian_to_int(result)), tx


def call_sample(state, validator_manager_addr, block_number, shard_id, sig_index):
    ct = get_valmgr_ct()
    dummy_addr = b'\xff' * 20
    return call_msg(
        state, ct, 'sample', [block_number, shard_id, sig_index],
        dummy_addr, validator_manager_addr
    )


def call_validation_code(state, validation_code_addr, msg_hash, signature):
    dummy_addr = b'\xff' * 20
    data = msg_hash + signature
    msg = vm.Message(dummy_addr, validation_code_addr, 0, 200000, data)
    # result == None if apply_message fails?!
    result = apply_message(state, msg)
    if not result:
        raise MessageFailed()
    return bool(utils.big_endian_to_int(result))


def sign(msg_hash, privkey):
    v, r, s = utils.ecsign(msg_hash, privkey)
    signature = utils.encode_int32(v) + utils.encode_int32(r) + utils.encode_int32(s)
    return signature


def test():
    deposit_size = 10 ** 20
    withdraw_hash = utils.sha3("withdraw")
    valmgr_sender_privkey = t.k0
    c = t.Chain()
    c.mine(1, coinbase=t.a0)
    c.head_state.gas_limit = 10 ** 10
    c.head_state.set_balance(address=t.a0, value=deposit_size * 10)
    c.head_state.set_balance(address=t.a1, value=deposit_size * 10)

    validator_manager_addr = deploy_valmgr_contract(c.head_state, valmgr_sender_privkey)
    k0_valcode_addr = deploy_contract(c.head_state, t.k0, serpent.compile(mk_validation_code(t.a0)))
    a = call_deposit(c.head_state, validator_manager_addr, t.k0, deposit_size, k0_valcode_addr, t.a2)
    print(a)
    a = call_sample(c.head_state, validator_manager_addr, 0, 1, 2)
    print(a)
    print(call_withdraw(c.head_state, validator_manager_addr, t.k0, 0, sign(withdraw_hash, t.k0)))
    a = call_sample(c.head_state, validator_manager_addr, 0, 1, 2)
    print(a)
    print(call_validation_code(c.head_state, k0_valcode_addr, withdraw_hash, sign(withdraw_hash, t.k0)))


if __name__ == '__main__':
    test()
