from ethereum.tools import tester as t
from ethereum import abi, utils, vm
from ethereum.messages import apply_transaction, apply_message
from ethereum.transactions import Transaction
import viper

from sharding.tools import tester

STARTGAS = 10 ** 8
GASPRICE = 0

validator_manager_code = open('contracts/validator_manager.v.py').read()
c = t.Chain()
x = c.contract(validator_manager_code, language='viper')
validator_manager_addr = x.address

c.mine(1, coinbase=t.a0)
deposit_size = 10 ** 20
c.head_state.gas_limit = 10 ** 10
c.head_state.set_balance(address=t.a0, value=deposit_size * 10)
c.head_state.set_balance(address=t.a1, value=deposit_size * 10)

_valmgr_ct = None
_valmgr_code = None

class TransactionFailed(Exception):

    pass


def get_valmgr_ct():
    global _valmgr_ct, validator_manager_code
    if not _valmgr_ct:
        _valmgr_ct = abi.ContractTranslator(
            viper.compiler.mk_full_signature(validator_manager_code)
        )
    return _valmgr_ct


def call_msg(state, ct, func, args, sender, to, value=0, startgas=STARTGAS):
    abidata = vm.CallData([utils.safe_ord(x) for x in ct.encode_function_call(func, args)])
    msg = vm.Message(sender, to, value, startgas, abidata)
    # result == None if apply_message fails?!
    result = apply_message(state, msg)
    return result


def call_tx(state, ct, func, args, sender, to, value=0, startgas=STARTGAS, gasprice=GASPRICE):
    # Transaction(nonce, gasprice, startgas, to, value, data, v=0, r=0, s=0)
    tx = Transaction(state.get_nonce(utils.privtoaddr(sender)), gasprice, startgas, to, value,
            ct.encode_function_call(func, args)
         )
    tx = tx.sign(sender)
    # refer to the tester.tx
    success, output = apply_transaction(state, tx)
    # TODO: need to append the tx to the chain.block
    if not success:
        raise TransactionFailed("Tx failed")
    return output, tx


def call_deposit_function(state, validator_manager_addr, validation_code_addr, return_addr, sender, value):
    ct = get_valmgr_ct()
    return call_tx(
        state, ct, 'deposit', [validation_code_addr, return_addr],
        sender, validator_manager_addr, value
    )


def call_withdraw_function(state, validator_manager_addr, validator_index, signature, sender):
    ct = get_valmgr_ct()
    return call_tx(
        state, ct, 'withdraw', [validation_code_addr, return_addr],
        sender, validator_manager_addr, value
    )


def call_sample_function(state, validator_manager_addr, block_number, shard_id, sig_index):
    addr = utils.privtoaddr(utils.sha3("test"))
    ct = get_valmgr_ct()
    return call_msg(
        state, ct, 'sample', [block_number, shard_id, sig_index],
        addr, validator_manager_addr
    )


def sign(msg_hash, privkey):
    v, r, s = utils.ecsign(msg_hash, privkey)
    signature = utils.encode_int32(v) + utils.encode_int32(r) + utils.encode_int32(s)
    return signature


ct = get_valmgr_ct()

a = call_deposit_function(c.head_state, validator_manager_addr, validator_manager_addr, validator_manager_addr, t.k0, deposit_size)
print(a)
a = call_sample_function(c.head_state, validator_manager_addr, 0, 1, 2)
print(a)
print(call_withdraw_function(c.head_state, validator_manager_addr, 0, sign(utils.sha3("withdraw"), t.k0), t.k0))

