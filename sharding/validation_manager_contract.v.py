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

biggest_validators_index: public(num)

# indexs of empty slots caused by the function `withdraw`
empty_slots_queue: num[num]

# the front index of the queue in empty_slots_queue
front: num

# the end index of the queue in empty_slots_queue
end: num


def is_queue_empty() -> bool:

    return (self.front == self.end)

def enqueue(index: num):

    self.empty_slots_queue[self.end] = index
    self.end += 1

def dequeue() -> num:

    if self.is_queue_empty():
        return -1
    temp = self.empty_slots_queue[self.front]
    self.front += 1
    return temp

def peek() -> num:

    if self.is_queue_empty():
        return -1
    return self.empty_slots_queue[self.front]

# TODO: Should have a rearrange_queue which is executed when the end reaches
#       a fairly large number to limit the memory usage of the array?!
#       However, viper seems not to allow variable iterations loop. So maybe
#       will be implemented in the future


def take_validators_empty_slot() -> num:

    if self.is_queue_empty():
        return self.biggest_validators_index
    return self.dequeue()

def release_validator_slot(index: num):

    self.enqueue(index)

def deposit(validation_code_addr: address, return_addr: address) -> num:

    # TODO: check for deposit to be equaled to a certain amount of ETH
    index = self.take_validators_empty_slot()
    self.validators[index] = {
        deposit: msg.value,
        validation_code_addr: validation_code_addr,
        return_addr: return_addr
    }
    if index == self.biggest_validators_index:
        self.biggest_validators_index += 1
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
        self.release_validator_slot(validator_index)
    return result

def sample(block_number: num, shard_id: num, sig_index: num) -> num:

    return self.biggest_validators_index

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

# test withdraw to fail when no validator record
assert not x.withdraw(0, sign(withdraw_msg_hash, t.k0))
# test deposit working fine
assert 0 == x.deposit(k0_valcode_addr, k0_valcode_addr)
assert 1 == x.deposit(k1_valcode_addr, k1_valcode_addr)
assert x.withdraw(0, sign(withdraw_msg_hash, t.k0))
# test deposit using empty slots
assert 0 == x.deposit(k1_valcode_addr, k1_valcode_addr)
assert x.withdraw(1, sign(withdraw_msg_hash, t.k1))
# test deposit working fine in the edge condition
assert 1 == x.deposit(k1_valcode_addr, k1_valcode_addr)
# test withdraw to fail when the signature is not corret
assert not x.withdraw(1, sign(withdraw_msg_hash, t.k0))
