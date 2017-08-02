# Information about validators
validators: public({
    # Amount of wei the validator holds
    deposit: wei_value,
    # The address which the validator's signatures must verify to (to be later replaced with validation code)
    validation_code_addr: address,
    # Addess to withdraw to
    return_addr: address,
}[num])

num_validators: public(num)

# indexs of empty slots caused by the function `withdraw`
empty_slots_stack: num[num]

# the top index of the stack in empty_slots_stack
empty_slots_stack_top: num

# the exact deposit size which you have to deposit to become a validator
deposit_size: wei_value

# any given validator randomly gets allocated to some number of shards every SHUFFLING_CYCLE
shuffling_cycle_length: num

# gas limit of the signature validation code
sig_gas_limit: num

# is a valcode addr deposited now?
is_valcode_deposited: bool[address]

period_length: num

shard_count: num

collator_reward: decimal

def __init__():
    self.num_validators = 0
    self.empty_slots_stack_top = 0
    # 10 ** 20 wei = 100 ETH
    self.deposit_size = 100000000000000000000
    self.shuffling_cycle_length = 2500
    self.sig_gas_limit = 400000
    self.period_length = 5
    self.shard_count = 100
    self.collator_reward = 0.002

def is_stack_empty() -> bool:
    return (self.empty_slots_stack_top == 0)


def stack_push(index: num):
    self.empty_slots_stack[self.empty_slots_stack_top] = index
    self.empty_slots_stack_top += 1


def stack_pop() -> num:
    if self.is_stack_empty():
        return -1
    self.empty_slots_stack_top -= 1
    return self.empty_slots_stack[self.empty_slots_stack_top]


def get_validators_max_index() -> num:
    return self.num_validators + self.empty_slots_stack_top


@payable
def deposit(validation_code_addr: address, return_addr: address) -> num:
    assert not self.is_valcode_deposited[validation_code_addr]
    assert msg.value == self.deposit_size
    # find the empty slot index in validators set
    if not self.is_stack_empty():
        index = self.stack_pop()
    else:
        index = self.num_validators
    self.validators[index] = {
        deposit: msg.value,
        validation_code_addr: validation_code_addr,
        return_addr: return_addr
    }
    self.num_validators += 1
    self.is_valcode_deposited[validation_code_addr] = True
    return index


def withdraw(validator_index: num, sig: bytes <= 1000) -> bool:
    msg_hash = sha3("withdraw")
    result = (extract32(raw_call(self.validators[validator_index].validation_code_addr, concat(msg_hash, sig), gas=self.sig_gas_limit, outsize=32), 0) == as_bytes32(1))
    if result:
        send(self.validators[validator_index].return_addr, self.validators[validator_index].deposit)
        self.is_valcode_deposited[self.validators[validator_index].validation_code_addr] = False
        self.validators[validator_index] = {
            deposit: 0,
            validation_code_addr: None,
            return_addr: None
        }
        self.stack_push(validator_index)
        self.num_validators -= 1
    return result


def sample(shard_id: num) -> address:
    zero_addr = 0x0000000000000000000000000000000000000000

    cycle = floor(decimal(block.number / self.shuffling_cycle_length))
    cycle_seed = blockhash(cycle * self.shuffling_cycle_length)
    seed = blockhash(block.number  - (block.number % self.period_length))
    index_in_subset = num256_mod(as_num256(sha3(concat(seed, as_bytes32(shard_id)))),
                                 as_num256(100))
    if self.num_validators != 0:
        # TODO: here we assume this fixed number of rounds is enough to sample
        #       out a validator
        for i in range(1024):
            validator_index = num256_mod(as_num256(sha3(concat(cycle_seed, as_bytes32(shard_id), as_bytes32(index_in_subset), as_bytes32(i)))),
                                         as_num256(self.get_validators_max_index()))
            addr = self.validators[as_num128(validator_index)].validation_code_addr
            if addr != zero_addr:
                return addr

    return zero_addr


