from ethereum import utils
from ethereum.slogging import LogRecorder, configure_logging, set_level
from ethereum.tools import tester as t
from ethereum.transactions import Transaction
import rlp
from rlp.sedes import binary, List
import serpent

config_string = ":info,:debug"
'''
from ethereum.slogging import LogRecorder, configure_logging, set_level
config_string = ':info,eth.vm.log:trace,eth.vm.op:trace,eth.vm.stack:trace,eth.vm.exit:trace,eth.pb.msg:trace,eth.pb.tx:debug'
configure_logging(config_string=config_string)
'''

viper_rlp_decoder_tx_hex = "0xf90237808506fc23ac00830330888080b902246102128061000e60003961022056600060007f010000000000000000000000000000000000000000000000000000000000000060003504600060c082121515585760f882121561004d5760bf820336141558576001905061006e565b600181013560f783036020035260005160f6830301361415585760f6820390505b5b368112156101c2577f010000000000000000000000000000000000000000000000000000000000000081350483602086026040015260018501945060808112156100d55760018461044001526001828561046001376001820191506021840193506101bc565b60b881121561014357608081038461044001526080810360018301856104600137608181141561012e5760807f010000000000000000000000000000000000000000000000000000000000000060018401350412151558575b607f81038201915060608103840193506101bb565b60c08112156101b857600182013560b782036020035260005160388112157f010000000000000000000000000000000000000000000000000000000000000060018501350402155857808561044001528060b6838501038661046001378060b6830301830192506020810185019450506101ba565bfe5b5b5b5061006f565b601f841315155857602060208502016020810391505b6000821215156101fc578082604001510182826104400301526020820391506101d8565b808401610420528381018161044003f350505050505b6000f31b2d4f"
viper_rlp_decoder_tx = rlp.decode(utils.parse_as_bin(viper_rlp_decoder_tx_hex), Transaction)
viper_rlp_decoder_addr = viper_rlp_decoder_tx.creates

sighasher_tx_hex = "0xf9016d808506fc23ac0083026a508080b9015a6101488061000e6000396101565660007f01000000000000000000000000000000000000000000000000000000000000006000350460f8811215610038576001915061003f565b60f6810391505b508060005b368312156100c8577f01000000000000000000000000000000000000000000000000000000000000008335048391506080811215610087576001840193506100c2565b60b881121561009d57607f8103840193506100c1565b60c08112156100c05760b68103600185013560b783036020035260005101840193505b5b5b50610044565b81810360388112156100f4578060c00160005380836001378060010160002060e052602060e0f3610143565b61010081121561010557600161011b565b6201000081121561011757600261011a565b60035b5b8160005280601f038160f701815382856020378282600101018120610140526020610140f350505b505050505b6000f31b2d4f"
sighasher_tx = rlp.decode(utils.parse_as_bin(sighasher_tx_hex), Transaction)
sighasher_addr = sighasher_tx.creates

validator_manager_code = open('validator_manager.v.py', 'r').read()

def sign(msg_hash, privkey):
    v, r, s = utils.ecsign(msg_hash, privkey)
    signature = utils.encode_int32(v) + utils.encode_int32(r) + utils.encode_int32(s)
    return signature


def mk_validation_code(address):
    validation_code = """
~calldatacopy(0, 0, 128)
~call(3000, 1, 0, 0, 128, 0, 32)
return(~mload(0) == {})
    """.format(utils.checksum_encode(address))
    return validation_code

# Must pay 100 ETH to become a validator
deposit_size = 10 ** 20
withdraw_msg_hash = utils.sha3("withdraw")

c = t.Chain()

k0_valcode_addr = c.tx(t.k0, '', 0, serpent.compile(mk_validation_code(t.a0)))
k1_valcode_addr = c.tx(t.k1, '', 0, serpent.compile(mk_validation_code(t.a1)))

c.mine(1, coinbase=t.a0)
c.head_state.gas_limit = 10 ** 12
x = c.contract(validator_manager_code, language='viper', startgas=10**11)
c.head_state.set_balance(address=t.a0, value=deposit_size * 10)
c.head_state.set_balance(address=t.a1, value=deposit_size * 10)
c.head_state.set_balance(address=viper_rlp_decoder_tx.sender, value=deposit_size * 10)
c.head_state.set_balance(address=sighasher_tx.sender, value=deposit_size * 10)
c.direct_tx(viper_rlp_decoder_tx)
c.direct_tx(sighasher_tx)

# test deposit: fails when msg.value != deposit_size
try:
    x.deposit(k0_valcode_addr, k0_valcode_addr)
    assert False
except t.TransactionFailed:
    pass
# test withdraw: fails when no validator record
assert not x.withdraw(0, sign(withdraw_msg_hash, t.k0))
# test deposit: works fine
assert 0 == x.deposit(k0_valcode_addr, k0_valcode_addr, value=deposit_size, sender=t.k0)
assert 1 == x.deposit(k1_valcode_addr, k1_valcode_addr, value=deposit_size, sender=t.k1)
assert x.withdraw(0, sign(withdraw_msg_hash, t.k0))
# test deposit: make use of empty slots
assert 0 == x.deposit(k0_valcode_addr, k0_valcode_addr, value=deposit_size, sender=t.k0)
assert x.withdraw(1, sign(withdraw_msg_hash, t.k1))
# test deposit: working fine in the edge condition
assert 1 == x.deposit(k1_valcode_addr, k1_valcode_addr, value=deposit_size, sender=t.k1)
# test deposit: fails when valcode_addr is deposited before
try:
    x.deposit(k1_valcode_addr, k1_valcode_addr, value=deposit_size, sender=t.k1)
    assert False
except t.TransactionFailed:
    pass
# test withdraw: fails when the signature is not corret
assert not x.withdraw(1, sign(withdraw_msg_hash, t.k0))

# test sample: correctly sample the only one validator
assert x.withdraw(0, sign(withdraw_msg_hash, t.k0))
assert x.sample(0) == hex(utils.big_endian_to_int(k1_valcode_addr))
# test sample: sample returns zero_addr (i.e. 0x00) when there is no depositing validator
assert x.withdraw(1, sign(withdraw_msg_hash, t.k1))
assert x.sample(0) == "0x0000000000000000000000000000000000000000"
assert 1 == x.deposit(k0_valcode_addr, k0_valcode_addr, value=deposit_size, sender=t.k0)

def get_colhdr(shard_id, parent_collation_hash):
    expected_period_number = 0
    period_start_prevhash = b"period  " * 4
    tx_list_root = b"tx_list " * 4
    collation_coinbase = t.a0
    post_state_root = b"post_sta" * 4
    receipt_root = b"receipt " * 4
    sighash = utils.sha3(
        rlp.encode([
            shard_id, expected_period_number, period_start_prevhash,
            parent_collation_hash, tx_list_root, collation_coinbase,
            post_state_root, receipt_root
        ])
    )
    sig = sign(sighash, t.k0)
    return rlp.encode([
        shard_id, expected_period_number, period_start_prevhash,
        parent_collation_hash, tx_list_root, collation_coinbase,
        post_state_root, receipt_root, sig
    ])


header_logs = []
add_header_topic = utils.big_endian_to_int(utils.sha3("add_header()"))
def header_event_watcher(log):
    global header_logs, add_header_topic
    # print the last log and store the recent received one
    if log.topics[0] == add_header_topic:
        # print(log.data)
        header_logs.append(log.data)
        if len(header_logs) > 1:
            last_log = header_logs.pop(0)
            # []
            # [num, num, bytes32, bytes32, bytes32, address, bytes32, bytes32, bytes]
            # use sedes to prevent integer 0 from being decoded as b''
            sedes = List([utils.big_endian_int, utils.big_endian_int, utils.hash32, utils.hash32, utils.hash32, utils.address, utils.hash32, utils.hash32, binary])
            values = rlp.decode(last_log, sedes)
            print("add_header: shard_id={}, expected_period_number={}, header_hash={}, parent_header_hash={}".format(values[0], values[1], utils.sha3(last_log), values[3]))


c.head_state.log_listeners.append(header_event_watcher)

# configure_logging(config_string=config_string)
shard_id = 0
shard0_genesis_colhdr_hash = utils.sha3(utils.encode_int32(shard_id) + b"GENESIS")

# test add_header: works normally with parent_collation_hash == GENESIS
h0 = get_colhdr(shard_id, shard0_genesis_colhdr_hash)
h0_hash = utils.sha3(h0)
assert x.add_header(h0)
# test add_header: fails when the header is added before
try:
    h0 = get_colhdr(shard_id, shard0_genesis_colhdr_hash)
    result = x.add_header(h0)
    assert False
except t.TransactionFailed:
    pass
# test add_header: fails when the parent_collation_hash is not added before
try:
    h1 = get_colhdr(shard_id, utils.sha3("123"))
    result = x.add_header(h1)
    assert False
except t.TransactionFailed:
    pass
# test  add_header: the log is generated normally
try:
    h1 = get_colhdr(shard_id, h0_hash)
    h1_hash = utils.sha3(h1)
    assert x.add_header(h1)
    latest_log_hash = utils.sha3(header_logs[-1])
    assert h1_hash == latest_log_hash
except (IndexError, t.TransactionFailed):
    assert False