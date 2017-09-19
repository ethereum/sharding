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
    parent_collation_hash: bytes32,
    score: num,
}[bytes32][num])

receipts: public({
    shard_id: num,
    tx_startgas: num,
    tx_gasprice: num,
    value: wei_value,
    sender: address,
    to: address,
    data: bytes <= 4096
}[num])

shard_head: public(bytes32[num])

num_validators: public(num)

num_receipts: num

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

num_validators_per_cycle: num

shard_count: num

add_header_log_topic: bytes32

sighasher_addr: address

def __init__():
    self.num_validators = 0
    self.empty_slots_stack_top = 0
    # 10 ** 20 wei = 100 ETH
    self.deposit_size = 100000000000000000000
    self.shuffling_cycle_length = 2500
    self.sig_gas_limit = 400000
    self.period_length = 5
    self.num_validators_per_cycle = 100
    self.shard_count = 100
    self.add_header_log_topic = sha3("add_header()")
    self.sighasher_addr = 0xDFFD41E18F04Ad8810c83B14FD1426a82E625A7D


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


@constant
def sample(shard_id: num) -> address:

    cycle = floor(decimal(block.number / self.shuffling_cycle_length))
    cycle_start_block_number = cycle * self.shuffling_cycle_length - 1
    if cycle_start_block_number < 0:
        cycle_start_block_number = 0
    cycle_seed = blockhash(cycle_start_block_number)
    # originally, error occurs when block.number <= 4 because
    # `seed_block_number` becomes negative in these cases.
    # Now, just reject the cases when block.number <= 4
    assert block.number >= self.period_length
    seed = blockhash(block.number - (block.number % self.period_length) - 1)
    index_in_subset = num256_mod(as_num256(sha3(concat(seed, as_bytes32(shard_id)))),
                                 as_num256(self.num_validators_per_cycle))
    validator_index = num256_mod(as_num256(sha3(concat(cycle_seed, as_bytes32(shard_id), as_bytes32(index_in_subset)))),
                                 as_num256(self.get_validators_max_index()))
    addr = self.validators[as_num128(validator_index)].validation_code_addr

    return addr


# Attempts to process a collation header, returns True on success, reverts on failure.
def add_header(header: bytes <= 4096) -> bool:
    zero_addr = 0x0000000000000000000000000000000000000000

    values = RLPList(header, [num, num, bytes32, bytes32, bytes32, address, bytes32, bytes32, bytes])
    shard_id = values[0]
    expected_period_number = values[1]
    period_start_prevhash = values[2]
    parent_collation_hash = values[3]
    tx_list_root = values[4]
    collation_coinbase = values[5]
    post_state_root = values[6]
    receipt_root = values[7]
    sig = values[8]

    # Check if the header is valid
    assert (shard_id >= 0) and (shard_id < self.shard_count)
    assert block.number >= self.period_length
    assert expected_period_number == floor(decimal(block.number / self.period_length))
    assert period_start_prevhash == blockhash(expected_period_number * self.period_length - 1)

    # Check if this header already exists
    entire_header_hash = sha3(header)
    assert entire_header_hash != as_bytes32(0)
    assert self.collation_headers[shard_id][entire_header_hash].score == 0
    # Check whether the parent exists.
    # if (parent_collation_hash == 0), i.e., is the genesis,
    # then there is no need to check.
    if parent_collation_hash != as_bytes32(0):
        assert (parent_collation_hash == as_bytes32(0)) or (self.collation_headers[shard_id][parent_collation_hash].score > 0)
    # Check the signature with validation_code_addr
    collator_valcode_addr = self.sample(shard_id)
    if collator_valcode_addr == zero_addr:
        return False
    sighash = extract32(raw_call(self.sighasher_addr, header, gas=200000, outsize=32), 0)
    assert extract32(raw_call(collator_valcode_addr, concat(sighash, sig), gas=self.sig_gas_limit, outsize=32), 0) == as_bytes32(1)

    # Add the header
    _score = self.collation_headers[shard_id][parent_collation_hash].score + 1
    self.collation_headers[shard_id][entire_header_hash] = {
        parent_collation_hash: parent_collation_hash,
        score: _score
    }

    # Determine the head
    if _score > self.collation_headers[shard_id][self.shard_head[shard_id]].score:
        self.shard_head[shard_id] = entire_header_hash

    # Emit log
    raw_log([self.add_header_log_topic], header)

    return True


@constant
def get_period_start_prevhash(expected_period_number: num) -> bytes32:
    block_number = expected_period_number * self.period_length - 1
    assert block.number > block_number
    return blockhash(block_number)


# Returns the 10000th ancestor of this hash.
# def get_ancestor(shard_id: num, hash: bytes32) -> bytes32:
#     colhdr = self.collation_headers[shard_id][hash]
#     # assure that the colhdr exists
#     assert colhdr.parent_collation_hash != as_bytes32(0)
#     genesis_colhdr_hash = sha3(concat(as_bytes32(shard_id), "GENESIS"))
#     current_colhdr_hash = hash
#     # get the 10000th ancestor
#     for i in range(10000):
#         assert current_colhdr_hash != genesis_colhdr_hash
#         current_colhdr_hash = self.collation_headers[shard_id][current_colhdr_hash].parent_collation_hash
#     return current_colhdr_hash


# Returns the difference between the block number of this hash and the block
# number of the 10000th ancestor of this hash.
@constant
def get_ancestor_distance(hash: bytes32) -> bytes32:
    # TODO: to be implemented
    pass


# Returns the gas limit that collations can currently have (by default make
# this function always answer 10 million).
@constant
def get_collation_gas_limit() -> num:
    return 10000000


# Records a request to deposit msg.value ETH to address to in shard shard_id
# during a future collation. Saves a `receipt ID` for this request,
# also saving `msg.sender`, `msg.value`, `to`, `shard_id`, `startgas`,
# `gasprice`, and `data`.
@payable
def tx_to_shard(to: address, shard_id: num, tx_startgas: num, tx_gasprice: num, data: bytes <= 4096) -> num:
    self.receipts[self.num_receipts] = {
        shard_id: shard_id,
        tx_startgas: tx_startgas,
        tx_gasprice: tx_gasprice,
        value: msg.value,
        sender: msg.sender,
        to: to,
        data: data
    }
    receipt_id = self.num_receipts
    self.num_receipts += 1
    return receipt_id


@payable
def update_gasprice(receipt_id: num, tx_gasprice: num) -> bool:
    assert self.receipts[receipt_id].sender == msg.sender
    self.receipts[receipt_id].tx_gasprice = tx_gasprice
    return True
