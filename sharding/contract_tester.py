from ethereum import utils
from ethereum.tools import tester as t
import serpent

validation_manager_code = """
data validator_set_size
data validator_set[](validator_addr, deposit, validation_code_addr, return_addr)

def init():
    self.validator_set_size = 0

# internal use: to find the index for the addr in the validator set
def get_validator_index(addr):
    index = 0
    while index < self.validator_set_size and addr != self.validator_set[index].validator_addr:
        index = index + 1
    return(index)

def deposit(validation_code_addr, return_addr):
    index = self.get_validator_index(msg.sender)
    self.validator_set[index].validator_addr = msg.sender
    self.validator_set[index].deposit = self.validator_set[index].deposit + msg.value
    self.validator_set[index].validation_code_addr = validation_code_addr
    self.validator_set[index].return_addr = return_addr
    if index == self.validator_set_size: # new validator
        self.validator_set_size = self.validator_set_size + 1
    return(index)

def withdraw():
    pass

def sample():
    pass

"""
msg_hash = utils.sha3("123")
print(len(msg_hash))
v, r, s = utils.ecsign(msg_hash, t.k0)

validator_addr = t.a0
validation_code = """
def test_ecrecover(h, v, r, s):
    return(ecrecover(h, v, r, s)) # confirm the addr matches the signature
"""
validation_code = """
~calldatacopy(0, 0, 128)
~call(3000, 1, 0, 0, 128, 0, 32)
return(~mload(0) == {})
""".format(utils.checksum_encode(validator_addr))

c = t.Chain()
vc = c.contract(validation_code, language='serpent')
#vmc = c.contract(validation_manager_code, language='serpent')
#result = vc.test_ecrecover(utils.big_endian_to_int(msg_hash), 1, 2, 3)
vc_data = serpent.compile(validation_code)
valcode_addr = c.tx(t.k0, '', 0, vc_data)
print(valcode_addr)
#print(x.deposit(1, 1))
