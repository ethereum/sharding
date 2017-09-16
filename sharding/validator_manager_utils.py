import os
import rlp
import viper

from ethereum import abi, utils, vm
from ethereum.messages import apply_message
from ethereum.transactions import Transaction

from sharding.config import sharding_config

STARTGAS = 3141592   # TODO: use config
GASPRICE = 1         # TODO: use config
DEPOSIT_SIZE = sharding_config['DEPOSIT_SIZE']
WITHDRAW_HASH = utils.sha3("withdraw")
ADD_HEADER_TOPIC = utils.sha3("add_header()")

_valmgr_ct = None
_valmgr_code = None
_valmgr_bytecode = None
_valmgr_addr = None
_valmgr_sender_addr = None
_valmgr_tx = None

viper_rlp_decoder_tx = rlp.decode(utils.parse_as_bin("0xf90237808506fc23ac00830330888080b902246102128061000e60003961022056600060007f010000000000000000000000000000000000000000000000000000000000000060003504600060c082121515585760f882121561004d5760bf820336141558576001905061006e565b600181013560f783036020035260005160f6830301361415585760f6820390505b5b368112156101c2577f010000000000000000000000000000000000000000000000000000000000000081350483602086026040015260018501945060808112156100d55760018461044001526001828561046001376001820191506021840193506101bc565b60b881121561014357608081038461044001526080810360018301856104600137608181141561012e5760807f010000000000000000000000000000000000000000000000000000000000000060018401350412151558575b607f81038201915060608103840193506101bb565b60c08112156101b857600182013560b782036020035260005160388112157f010000000000000000000000000000000000000000000000000000000000000060018501350402155857808561044001528060b6838501038661046001378060b6830301830192506020810185019450506101ba565bfe5b5b5b5061006f565b601f841315155857602060208502016020810391505b6000821215156101fc578082604001510182826104400301526020820391506101d8565b808401610420528381018161044003f350505050505b6000f31b2d4f"), Transaction)
viper_rlp_decoder_addr = viper_rlp_decoder_tx.creates

sighasher_tx = rlp.decode(utils.parse_as_bin("0xf9016d808506fc23ac0083026a508080b9015a6101488061000e6000396101565660007f01000000000000000000000000000000000000000000000000000000000000006000350460f8811215610038576001915061003f565b60f6810391505b508060005b368312156100c8577f01000000000000000000000000000000000000000000000000000000000000008335048391506080811215610087576001840193506100c2565b60b881121561009d57607f8103840193506100c1565b60c08112156100c05760b68103600185013560b783036020035260005101840193505b5b5b50610044565b81810360388112156100f4578060c00160005380836001378060010160002060e052602060e0f3610143565b61010081121561010557600161011b565b6201000081121561011757600261011a565b60035b5b8160005280601f038160f701815382856020378282600101018120610140526020610140f350505b505050505b6000f31b2d4f"), Transaction)
sighasher_addr = sighasher_tx.creates


class MessageFailed(Exception):
    pass


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


def create_valmgr_tx(gasprice=GASPRICE):
    global _valmgr_sender_addr, _valmgr_addr, _valmgr_tx
    bytecode = get_valmgr_bytecode()
    tx = Transaction(0, gasprice, 4000000, to=b'', value=0, data=bytecode)
    tx.v = 27
    tx.r = 1000000000000000000000000000000000000000000000000000000000000000000000000000
    tx.s = 1000000000000000000000000000000000000000000000000000000000000000000000000000
    valmgr_sender_addr = extract_sender_from_tx(tx)
    valmgr_addr = utils.mk_contract_address(valmgr_sender_addr, 0)
    _valmgr_sender_addr = valmgr_sender_addr
    _valmgr_addr = valmgr_addr
    _valmgr_tx = tx


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


def call_tx(state, ct, func, args, sender, to, value=0, startgas=STARTGAS, gasprice=GASPRICE):
    # Transaction(nonce, gasprice, startgas, to, value, data, v=0, r=0, s=0)
    tx = Transaction(
        state.get_nonce(utils.privtoaddr(sender)), gasprice, startgas, to, value,
        ct.encode_function_call(func, args)
    ).sign(sender)
    return tx


def call_deposit(state, sender_privkey, value, validation_code_addr, return_addr):
    ct = get_valmgr_ct()
    return call_tx(
        state, ct, 'deposit', [validation_code_addr, return_addr],
        sender_privkey, get_valmgr_addr(), value
    )


def call_withdraw(state, sender_privkey, value, validator_index, signature):
    ct = get_valmgr_ct()
    return call_tx(
        state, ct, 'withdraw', [validator_index, signature],
        sender_privkey, get_valmgr_addr(), value
    )


def call_tx_add_header(state, sender_privkey, value, header):
    return call_tx(
        state, get_valmgr_ct(), 'add_header', [header],
        sender_privkey, get_valmgr_addr(), value
    )


def call_tx_to_shard(state, sender_privkey, value, to, shard_id, startgas, gasprice, data):
    return call_tx(
        state, get_valmgr_ct(), 'tx_to_shard', [to, shard_id, startgas, gasprice, data],
        sender_privkey, get_valmgr_addr(), value
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


def mk_initiating_contracts(sender_privkey, sender_starting_nonce):
    """Make transactions of createing initial contracts
    Including rlp_decoder, sighasher and validator_manager
    """
    o = []
    nonce = sender_starting_nonce
    global viper_rlp_decoder_tx, sighasher_tx
    # the sender gives all senders of the txs money, and append the
    # money-giving tx with the original tx to the return list
    for tx in (viper_rlp_decoder_tx, sighasher_tx, get_valmgr_tx()):
        o.append(Transaction(nonce, GASPRICE, 90000, tx.sender, tx.startgas * tx.gasprice + tx.value, '').sign(sender_privkey))
        o.append(tx)
        nonce += 1
    return o


def create_contract_tx(state, sender_privkey, bytecode, startgas=STARTGAS):
    """Generate create contract transaction
    """
    tx = Transaction(
        state.get_nonce(utils.privtoaddr(sender_privkey)),
        GASPRICE, startgas, to=b'', value=0,
        data=bytecode
    ).sign(sender_privkey)
    return tx


def call_valmgr(state, func, args, value=0, startgas=None, sender_addr=b'\x00' * 20):
    if startgas is None:
        startgas = sharding_config['CONTRACT_CALL_GAS']['VALIDATOR_MANAGER'][func]
    return call_contract_constantly(
        state, get_valmgr_ct(), get_valmgr_addr(), func, args,
        value=value, startgas=startgas, sender_addr=sender_addr
    )


def is_valmgr_setup(state):
    return not (b'' == state.get_code(get_valmgr_addr()) and
        0 == state.get_nonce(get_valmgr_sender_addr())
    )

