from ethereum import utils
from ethereum.tools import tester as t
import serpent

validation_manager_code = """
data validator_set_size
data validator_set[](deposit, validation_code_addr, return_addr)

def init():
    self.validator_set_size = 0

def deposit(validation_code_addr, return_addr):
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
privkey = t.k2
pubkey = utils.privtoaddr(privkey)
msg_hash = utils.sha3("withdraw")
v, r, s = utils.ecsign(msg_hash, privkey)

validator_addr = pubkey
validation_code = """
def test_ecrecover(h, v, r, s):
    return(ecrecover(h, v, r, s) == {}) # confirm the addr matches the signature
""".format(utils.checksum_encode(validator_addr))

c = t.Chain()
vc = c.contract(validation_code, language='serpent')
vmc = c.contract(validation_manager_code, language='serpent')
result = vc.test_ecrecover(msg_hash, v, r, s)
print(result)
