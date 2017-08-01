from ethereum import utils
from ethereum.tools import tester as t
import serpent

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

x = c.contract(validator_manager_code, language='viper')

c.mine(1, coinbase=t.a0)
c.head_state.gas_limit = 10 ** 10
c.head_state.set_balance(address=t.a0, value=deposit_size * 10)
c.head_state.set_balance(address=t.a1, value=deposit_size * 10)

# test deposit to fail when msg.value != deposit_size
try:
    x.deposit(k0_valcode_addr, k0_valcode_addr)
    assert False
except t.TransactionFailed:
    pass
# test withdraw to fail when no validator record
assert not x.withdraw(0, sign(withdraw_msg_hash, t.k0))
# test deposit working fine
assert 0 == x.deposit(k0_valcode_addr, k0_valcode_addr, value=deposit_size, sender=t.k0)
assert 1 == x.deposit(k1_valcode_addr, k1_valcode_addr, value=deposit_size, sender=t.k1)
assert x.withdraw(0, sign(withdraw_msg_hash, t.k0))
# test deposit using empty slots
assert 0 == x.deposit(k0_valcode_addr, k0_valcode_addr, value=deposit_size, sender=t.k0)
assert x.withdraw(1, sign(withdraw_msg_hash, t.k1))
# test deposit working fine in the edge condition
assert 1 == x.deposit(k1_valcode_addr, k1_valcode_addr, value=deposit_size, sender=t.k1)
# test that deposit should fail when valcode_addr is deposited before
try:
    x.deposit(k1_valcode_addr, k1_valcode_addr, value=deposit_size, sender=t.k1)
    assert False
except t.TransactionFailed:
    pass
# test withdraw to fail when the signature is not corret
assert not x.withdraw(1, sign(withdraw_msg_hash, t.k0))

# test sample
assert x.withdraw(0, sign(withdraw_msg_hash, t.k0))
assert x.sample(0) == hex(utils.big_endian_to_int(k1_valcode_addr))
assert x.withdraw(1, sign(withdraw_msg_hash, t.k1))
assert x.sample(0) == "0x0000000000000000000000000000000000000000"
