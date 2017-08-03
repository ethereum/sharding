# Information about validators
validators: public({
    # Amount of wei the validator holds
    deposit: wei_value,
    # The address which the validator's signatures must verify to (to be later replaced with validation code)
    validation_code_addr: address,
    # Addess to withdraw to
    return_addr: address,
}[num])

collation_headers: public({
    shard_id: num,
    hash: bytes32,
    parent_hash: bytes32,
    score: num,
}[bytes32][num])

shard_head: bytes32[num]

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

add_header_log_topic: bytes32

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
    self.add_header_log_topic = sha3("add_header()")
    # Initialize all genesis header for all shards
    for i in range(100):
        genesis_header_hash = sha3(concat(as_bytes32(i), "GENESIS"))
        self.collation_headers[i][genesis_header_hash] = {
            shard_id: i,
            hash: genesis_header_hash,
            parent_hash: genesis_header_hash,
            score: 0
        }
        self.shard_head[i] = genesis_header_hash


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


# Attempts to process a collation header, returns True on success, reverts on failure.
def add_header(header: bytes <= 4096) -> bool:
    # shardId: uint256,
    # expected_period_number: uint256,
    # period_start_prevhash: bytes32,
    # parent_collation_hash: bytes32,
    # tx_list_root: bytes32,
    # coinbase: address,
    # post_state_root: bytes32,
    # receipt_root: bytes32,
    # sig: bytes

    # TODO: deserialize the header using RLPList
    # values = RLPList(header, [num, num, bytes32, bytes32, bytes32, address, bytes32, bytes32, bytes])
    shard_id = as_num128(extract32(slice(header, start=0, len=32), 0))
    expected_period_number = as_num128(extract32(slice(header, start=32, len=32), 0))
    period_start_prevhash = extract32(slice(header, start=64, len=32), 0)
    parent_collation_hash = extract32(slice(header, start=96, len=32), 0)
    tx_list_root = extract32(slice(header, start=128, len=32), 0)
    # FIXME: leave the coinbase alone now
    collation_coinbase = slice(header, start=160, len=20)
    post_state_root = extract32(slice(header, start=180, len=32), 0)
    receipt_root = extract32(slice(header, start=212, len=32), 0)
    len_data = 32 * 5 + 20 + 32 * 2
    len_sig = len(header) - len_data
    sig = slice(header, start=len_data, len=len_sig)

    # Check if the header is valid
    assert shard_id >= 0
    assert expected_period_number == floor(decimal(block.number / self.period_length))
    # Check if the parent hash exists
    assert self.collation_headers[shard_id][parent_collation_hash].hash != as_bytes32(0)
    # Check the signature with validation_code_addr
    data_hash = sha3(slice(header, start=0, len=len_data))
    collator_valcode_addr = self.sample(shard_id)
    assert extract32(raw_call(collator_valcode_addr, concat(data_hash, sig), gas=self.sig_gas_limit, outsize=32), 0) == as_bytes32(1)

    # Add the header
    entire_header_hash = sha3(header)
    _score = self.collation_headers[shard_id][parent_collation_hash].score + 1
    self.collation_headers[shard_id][parent_collation_hash] = {
        shard_id: shard_id,
        # FIXME: We should use the hash of the result of rlp_encode(header) as the header hash
        hash: entire_header_hash,
        parent_hash: parent_collation_hash,
        score: _score
    }

    # Determine the head
    if _score > self.collation_headers[shard_id][self.shard_head[shard_id]].score:
        self.shard_head[shard_id] = entire_header_hash

    # TODO: Emit log
    raw_log([self.add_header_log_topic], header)

    return True


# Returns the header hash that is the head of a given shard as perceived by
# the manager contract.
def get_head(shard_id: num) -> bytes32:
    return self.shard_head[shard_id]


# Returns the 10000th ancestor of this hash.
def get_ancestor(hash: bytes32) -> bytes32:
    pass


# Returns the difference between the block number of this hash and the block
# number of the 10000th ancestor of this hash.
def get_ancestor_distance(hash: bytes32) -> bytes32:
    pass


# Returns the gas limit that collations can currently have (by default make
# this function always answer 10 million).
def get_collation_gas_limit() -> num:
    return 10000000

