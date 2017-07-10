from ethereum import utils
from ethereum.tools import tester as t
import serpent
import secp256k1

validation_manager_code = """
data validator_set_size
data validator_set[](deposit, validation_code_addr, return_addr)

def init():
    self.validator_set_size = 0

def deposit(validation_code_addr, return_addr):
    index = self.validator_set_size
    self.validator_set[index].deposit = msg.value
    self.validator_set[index].validation_code_addr = validation_code_addr
    self.validator_set[index].return_addr = return_addr
    self.validator_set_size = self.validator_set_size + 1
    return(index)

def withdraw(validator_index, sig):
    # store sha3("withdraw") to memory[0~31]
    ~mstore(0, sha3("withdraw"))
    # copy tx_data[40~40+96-1] to memory[32]
    ~calldatacopy(32, 40 ,96)
    # call(gas, addr, value, in_data_mem_addr, in_data_size(128 bytes),
    #       out_data_mem_addr,out_data_size(32 bytes))
    ~call(200000, validationCodeAddr, 0, 0, 128, 0, 32)
    is_valid = ~mload(0)
    if is_valid:
        send(self.validator_set[validator_index].return_addr, self.validator_set[validator_index].deposit)
    return(is_valid)

def sample(seed, shard_id, sig_index):
    # TODO: returns a fixed result for easy testing
    return(self.validator_set_size)

"""
privkey = t.k0
pubkey = utils.privtoaddr(privkey)
msg_hash = utils.sha3("withdraw")

pk = secp256k1.PrivateKey(privkey, raw=True)
signature = pk.ecdsa_recoverable_serialize(
    pk.ecdsa_sign_recoverable(msg_hash, raw=True)
)
signature = signature[0] + bytes([signature[1]])
validator_addr = pubkey

validation_code = """~calldatacopy(0, 0, 128)
~call(3000, 1, 0, 0, 128, 0, 32)
return(~mload(0) == {})
""".format(utils.checksum_encode(validator_addr))

c = t.Chain()
vc_data = serpent.compile(validation_code) # equals to the data in tx
valcode_addr = c.tx(t.k0, '', 0, vc_data)

#vcc = c.contract(validation_code, language='serpent')
vmcc = c.contract(validation_manager_code, language='serpent')
index = vmcc.deposit(valcode_addr, 0x123)
print(vmcc.withdraw(0, signature))
