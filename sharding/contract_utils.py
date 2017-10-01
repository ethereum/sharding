import rlp

from ethereum import (
    utils,
    vm,
)
from ethereum.messages import apply_message
from ethereum.transactions import Transaction


STARTGAS = 3141592   # TODO: use config
GASPRICE = 1         # TODO: use config


class MessageFailed(Exception):
    pass


def sign(msg_hash, privkey):
    v, r, s = utils.ecsign(msg_hash, privkey)
    signature = utils.encode_int32(v) + utils.encode_int32(r) + utils.encode_int32(s)
    return signature


def get_tx_rawhash(tx, network_id=None):
    """Get a tx's rawhash.
       Copied from ethereum.transactions.Transaction.sign
    """
    if network_id is None:
        rawhash = utils.sha3(rlp.encode(tx, Transaction.exclude(['v', 'r', 's'])))
    else:
        assert 1 <= network_id < 2**63 - 18
        rlpdata = rlp.encode(rlp.infer_sedes(tx).serialize(tx)[:-3] + [network_id, b'', b''])
        rawhash = utils.sha3(rlpdata)
    return rawhash


def extract_sender_from_tx(tx):
    tx_rawhash = get_tx_rawhash(tx)
    return utils.sha3(
        utils.ecrecover_to_pub(tx_rawhash, tx.v, tx.r, tx.s)
    )[-20:]


def call_msg(state, ct, func, args, sender_addr, to, value=0, startgas=STARTGAS):
    abidata = vm.CallData([utils.safe_ord(x) for x in ct.encode_function_call(func, args)])
    msg = vm.Message(sender_addr, to, value, startgas, abidata)
    result = apply_message(state, msg)
    if result is None:
        raise MessageFailed("Msg failed")
    if result is False:
        return result
    if result == b'':
        return None
    o = ct.decode(func, result)
    return o[0] if len(o) == 1 else o


def call_contract_constantly(state, ct, contract_addr, func, args, value=0, startgas=200000, sender_addr=b'\x00' * 20):
    return call_msg(
        state.ephemeral_clone(), ct, func, args,
        sender_addr, contract_addr, value, startgas
    )


def call_contract_inconstantly(state, ct, contract_addr, func, args, value=0, startgas=200000, sender_addr=b'\x00' * 20):
    result = call_msg(
        state, ct, func, args, sender_addr, contract_addr, value, startgas
    )
    state.commit()
    return result


def call_tx(state, ct, func, args, sender, to, value=0, startgas=STARTGAS, gasprice=GASPRICE, nonce=None):
    # Transaction(nonce, gasprice, startgas, to, value, data, v=0, r=0, s=0)
    tx = Transaction(
        state.get_nonce(utils.privtoaddr(sender)) if nonce is None else nonce,
        gasprice, startgas, to, value,
        ct.encode_function_call(func, args)
    ).sign(sender)
    return tx


def create_contract_tx(state, sender_privkey, bytecode, startgas=STARTGAS):
    """Generate create contract transaction
    """
    tx = Transaction(
        state.get_nonce(utils.privtoaddr(sender_privkey)),
        GASPRICE, startgas, to=b'', value=0,
        data=bytecode
    ).sign(sender_privkey)
    return tx
