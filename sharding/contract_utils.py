import os

from ethereum.tools import tester as t
from ethereum import abi, utils, vm
from ethereum.messages import apply_transaction, apply_message
from ethereum.transactions import Transaction
import viper
import rlp

STARTGAS = 10 ** 8
GASPRICE = 0

_valmgr_ct = None
_valmgr_code = None
_valmgr_bytecode = None
_valmgr_addr = None
_valmgr_sender_addr = None
_valmgr_tx = None


class MessageFailed(Exception):

    pass


class TransactionFailed(Exception):

    pass


def get_valmgr_ct():
    global _valmgr_ct, _valmgr_code
    if not _valmgr_ct:
        _valmgr_ct = abi.ContractTranslator(
            viper.compiler.mk_full_signature(get_valmgr_code())
        )
    return _valmgr_ct


def get_valmgr_code():
    global _valmgr_code
    if not _valmgr_code:
        mydir = os.path.dirname(__file__)
        valmgr_path = os.path.join(mydir, 'contracts/validator_manager.v.py')
        _valmgr_code = open(valmgr_path).read()
    return _valmgr_code


def get_valmgr_bytecode():
    global _valmgr_bytecode
    if not _valmgr_bytecode:
        _valmgr_bytecode = viper.compiler.compile(get_valmgr_code())
    return _valmgr_bytecode


def get_valmgr_addr():
    global _valmgr_addr
    if not _valmgr_addr:
        create_valmgr_tx()
    return _valmgr_addr


def get_valmgr_sender_addr():
    global _valmgr_sender_addr
    if not _valmgr_sender_addr:
        create_valmgr_tx()
    return _valmgr_sender_addr


def get_valmgr_tx():
    global _valmgr_tx
    if not _valmgr_tx:
        create_valmgr_tx()
    return _valmgr_tx


def get_tx_rawhash(tx, network_id = None):
    """Get a tx's rawhash.
       Copied from ethereum.transactions.Transaction.sign
    """
    UnsignedTransaction = Transaction.exclude(['v', 'r', 's'])
    if network_id is None:
        rawhash = utils.sha3(rlp.encode(tx, UnsignedTransaction))
    else:
        assert 1 <= network_id < 2**63 - 18
        rlpdata = rlp.encode(rlp.infer_sedes(tx).serialize(tx)[:-3] + [network_id, b'', b''])
        rawhash = utils.sha3(rlpdata)
    return rawhash


def create_valmgr_tx(gasprice=GASPRICE, startgas=STARTGAS):
    global _valmgr_sender_addr, _valmgr_addr, _valmgr_tx
    bytecode = get_valmgr_bytecode()
    tx = Transaction(0 , gasprice, startgas, to=b'', value = 0, data=bytecode)
    tx.v = 28
    tx.r = 88211215265987573091860955075888007489896784216713220703632101173354667862905
    tx.s = 28950657277437913171015320570732318474400661424224137404770861665571343423479
    tx_rawhash = get_tx_rawhash(tx)
    valmgr_sender_addr = utils.sha3(
        utils.ecrecover_to_pub(tx_rawhash, tx.v, tx.r, tx.s)
    )[-20:]
    valmgr_addr = utils.mk_contract_address(valmgr_sender_addr, 0)
    _valmgr_sender_addr = valmgr_sender_addr
    _valmgr_addr = valmgr_addr
    _valmgr_tx = tx


def call_msg(state, ct, func, args, sender_addr, to, value=0, startgas=STARTGAS):
    abidata = vm.CallData([utils.safe_ord(x) for x in ct.encode_function_call(func, args)])
    msg = vm.Message(sender_addr, to, value, startgas, abidata)
    result = apply_message(state.ephemeral_clone(), msg)
    if result is None:
        raise MessageFailed("Msg failed")
    return result


def call_tx(state, ct, func, args, sender, to, value=0, startgas=STARTGAS, gasprice=GASPRICE):
    # Transaction(nonce, gasprice, startgas, to, value, data, v=0, r=0, s=0)
    tx = Transaction(state.get_nonce(utils.privtoaddr(sender)), gasprice, startgas, to, value,
            ct.encode_function_call(func, args)
         ).sign(sender)
    return tx


def call_deposit(state, validator_manager_addr, sender_privkey, value, validation_code_addr, return_addr):
    ct = get_valmgr_ct()
    return call_tx(
        state, ct, 'deposit', [validation_code_addr, return_addr],
        sender_privkey, validator_manager_addr, value
    )


def call_withdraw(state, validator_manager_addr, sender_privkey, validator_index, signature):
    ct = get_valmgr_ct()
    return call_tx(
        state, ct, 'withdraw', [validator_index, signature],
        sender_privkey, validator_manager_addr, 0
    )


def call_sample(state, validator_manager_addr, shard_id):
    ct = get_valmgr_ct()
    dummy_addr = b'\xff' * 20
    return call_msg(
        state, ct, 'sample', [shard_id],
        dummy_addr, validator_manager_addr
    )


def call_validation_code(state, validation_code_addr, msg_hash, signature):
    """Call validationCodeAddr on the main shard with 200000 gas, 0 value,
    the block_number concatenated with the sigIndex'th signature as input data gives output 1.
    """
    dummy_addr = b'\xff' * 20
    data = msg_hash + signature
    msg = vm.Message(dummy_addr, validation_code_addr, 0, 200000, data)
    result = apply_message(state.ephemeral_clone(), msg)
    if result is None:
        raise MessageFailed()
    return bool(utils.big_endian_to_int(result))


# Testing Part
def deploy_tx(state, tx):
    success, output = apply_transaction(state, tx)
    if not success:
        raise TransactionFailed("Failed to deploy tx")
    return output


def deploy_contract(state, sender_privkey, bytecode):
    tx = Transaction(
            state.get_nonce(utils.privtoaddr(sender_privkey)),
            GASPRICE, STARTGAS, to=b'', value=0,
            data=bytecode
    ).sign(sender_privkey)
    return deploy_tx(state, tx)


def deploy_valmgr_contract(state):
    addr = get_valmgr_addr()
    if not state.account_exists(addr):
        deploy_tx(state, _valmgr_tx)
    return addr


def mk_validation_code(address):
    '''
    validation_code = """
~calldatacopy(0, 0, 128)
~call(3000, 1, 0, 0, 128, 0, 32)
return(~mload(0) == {})
    """.format(utils.checksum_encode(address))
    return serpent.compile(validation_code)
    '''
    # The precompiled bytecode of the validation code which
    # verifies EC signatures
    validation_code_bytecode = b"a\x009\x80a\x00\x0e`\x009a\x00GV`\x80`\x00`\x007` "
    validation_code_bytecode += b"`\x00`\x80`\x00`\x00`\x01a\x0b\xb8\xf1Ps"
    validation_code_bytecode += address
    validation_code_bytecode += b"`\x00Q\x14` R` ` \xf3[`\x00\xf3"
    return validation_code_bytecode


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
    state = c.head_state
    state.gas_limit = 10 ** 10
    state.set_balance(address=t.a0, value=deposit_size * 10)
    state.set_balance(address=t.a1, value=deposit_size * 10)

    validator_manager_addr = deploy_valmgr_contract(state)
    k0_valcode_addr = deploy_contract(state, t.k0, mk_validation_code(t.a0))
    tx = call_deposit(state, validator_manager_addr, t.k0, deposit_size, k0_valcode_addr, t.a2)
    print(deploy_tx(state, tx))
    a = call_sample(state, validator_manager_addr, 0)
    print(a)
    tx = call_withdraw(state, validator_manager_addr, t.k0, 0, sign(withdraw_hash, t.k0))
    print(deploy_tx(state, tx))
    a = call_sample(state, validator_manager_addr, 0)
    print(a)
    print(call_validation_code(state, k0_valcode_addr, withdraw_hash, sign(withdraw_hash, t.k0)))


if __name__ == '__main__':
    test()
