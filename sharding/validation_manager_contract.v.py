from ethereum import utils
from ethereum.tools import tester as t
import serpent

validation_manager_code = """
validators: public({
    # Amount of wei the validator holds
    deposit: wei_value,
    # The address which the validator's signatures must verify to (to be later replaced with validation code)
    validation_code_addr: address,
    # Addess to withdraw to
    return_addr: address,
}[num])

num_validators: public(num)

def deposit(validation_code_addr: address, return_addr: address) -> num:

    index = self.num_validators
    self.validators[index] = {
        deposit: msg.value,
        validation_code_addr: validation_code_addr,
        return_addr: return_addr
    }
    self.num_validators += 1
    return index

def withdraw(validator_index: num, sig: bytes <= 1000) -> bool:

    msg_hash = sha3("withdraw")
    result = (extract32(raw_call(self.validators[validator_index].return_addr, concat(msg_hash, sig), gas=200000, outsize=32), 0) == as_bytes32(1))
    if result:
        send(self.validators[validator_index].return_addr, self.validators[validator_index].deposit)
        self.validators[validator_index] = {
            deposit: 0,
            validation_code_addr: None,
            return_addr: None
        }
    return result

def sample(block_number: num, shard_id: num, sig_index: num) -> num:

    return self.num_validators
"""

def sign(msg_hash, privkey):

    v, r, s = utils.ecsign(msg_hash, privkey)
    signature = utils.encode_int32(v) + utils.encode_int32(r) + utils.encode_int32(s)
    return signature

withdraw_msg_hash = utils.sha3("withdraw")

def mk_validation_code(address):
    validation_code = """
~calldatacopy(0, 0, 128)
~call(3000, 1, 0, 0, 128, 0, 32)
return(~mload(0) == {})
    """.format(utils.checksum_encode(address))
    return validation_code

c = t.Chain()

k0_valcode_addr = c.tx(t.k0, '', 0, serpent.compile(mk_validation_code(t.a0)))
k1_valcode_addr = c.tx(t.k1, '', 0, serpent.compile(mk_validation_code(t.a1)))

x = c.contract(validation_manager_code, language='viper')

assert 0 == x.deposit(k0_valcode_addr, k0_valcode_addr)
assert x.withdraw(0, sign(withdraw_msg_hash, t.k0))
assert 1 == x.deposit(k1_valcode_addr, k1_valcode_addr)
