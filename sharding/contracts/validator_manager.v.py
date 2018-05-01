# NOTE: Some variables are set as public variables for testing. They should be reset
# to private variables in an official deployment of the contract. 

#
# Events
#

RegisterNotary: __log__({index_in_notary_pool: int128, notary: address})
DeregisterNotary: __log__({index_in_notary_pool: int128, notary: address, deregistered_period: int128})
ReleaseNotary: __log__({index_in_notary_pool: int128, notary: address})


#
# State Variables
#

# Notary pool
# - notary_pool: array of active notary addresses
# - notary_pool_len: size of the notary pool
# - empty_slots_stack: stack of empty notary slot indices
# - empty_slots_stack_top: top index of the stack
notary_pool: public(address[int128])
notary_pool_len: public(int128)
empty_slots_stack: public(int128[int128])
empty_slots_stack_top: public(int128)

# Notary registry
# - deregistered: the period when the notary deregister. It defaults to 0 for not yet deregistered notarys
# - pool_index: indicates notary's index in the notary pool
notary_registry: {
    deregistered: int128,
    pool_index: int128
}[address]
# - does_notary_exist: returns true if notary's record exist in notary registry
does_notary_exist: public(bool[address])

# Notary sampling info
# In order to keep sample size unchanged through out entire period, we keep track of pool size change
# resulted from notary regitration/deregistration in current period and apply the change until next period. 
# - current_period_notary_sample_size: 
# - next_period_notary_sample_size: 
# - notary_sample_size_updated_period: latest period when current_period_notary_sample_size is updated
current_period_notary_sample_size: public(int128)
next_period_notary_sample_size: public(int128)
notary_sample_size_updated_period: public(int128)


#
# Configuration Parameters
# 

# The total number of shards within a network.
# Provisionally SHARD_COUNT := 100 for the phase 1 testnet.
SHARD_COUNT: int128

# The period of time, denominated in main chain block times, during which
# a collation tree can be extended by one collation.
# Provisionally PERIOD_LENGTH := 5, approximately 75 seconds.
PERIOD_LENGTH: int128

# The lookahead time, denominated in periods, for eligible collators to
# perform windback and select proposals.
# Provisionally LOOKAHEAD_LENGTH := 4, approximately 5 minutes.
LOOKAHEAD_LENGTH: int128

# The number of notaries to select from notary pool for each shard in each period.
COMMITTEE_SIZE: int128

# The threshold(number of notaries in committee) for a proposal to be deem accepted
QUORUM_SIZE: int128

# The fixed-size deposit, denominated in ETH, required for registration.
# Provisionally COLLATOR_DEPOSIT := 1000 and PROPOSER_DEPOSIT := 1.
NOTARY_DEPOSIT: wei_value

# The amount of time, denominated in periods, a deposit is locked up from the
# time of deregistration.
# Provisionally COLLATOR_LOCKUP_LENGTH := 16128, approximately two weeks, and
# PROPOSER_LOCKUP_LENGTH := 48, approximately one hour.
NOTARY_LOCKUP_LENGTH: int128


@public
def __init__(
        _SHARD_COUNT: int128,
        _PERIOD_LENGTH: int128,
        _LOOKAHEAD_LENGTH: int128,
        _COMMITTEE_SIZE: int128,
        _QUORUM_SIZE: int128,
        _NOTARY_DEPOSIT: wei_value,
        _NOTARY_LOCKUP_LENGTH: int128,
    ):
    self.SHARD_COUNT = _SHARD_COUNT
    self.PERIOD_LENGTH = _PERIOD_LENGTH
    self.LOOKAHEAD_LENGTH = _LOOKAHEAD_LENGTH
    self.COMMITTEE_SIZE = _COMMITTEE_SIZE
    self.QUORUM_SIZE = _QUORUM_SIZE
    self.NOTARY_DEPOSIT = _NOTARY_DEPOSIT
    self.NOTARY_LOCKUP_LENGTH = _NOTARY_LOCKUP_LENGTH


# Checks if empty_slots_stack_top is empty
@private
def is_empty_slots_stack_empty() -> bool:
    return (self.empty_slots_stack_top == 0)


# Pushes one int128 to empty_slots_stack
@private
def empty_slots_stack_push(index: int128):
    self.empty_slots_stack[self.empty_slots_stack_top] = index
    self.empty_slots_stack_top += 1


# Pops one int128 out of empty_slots_stack
@private
def empty_slots_stack_pop() -> int128:
    if self.is_empty_slots_stack_empty():
        return -1
    self.empty_slots_stack_top -= 1
    return self.empty_slots_stack[self.empty_slots_stack_top]


# Helper functions to get notary info in notary_registry
@public
@constant
def get_notary_info(notary_address: address) -> (int128, int128):
    return (self.notary_registry[notary_address].deregistered, self.notary_registry[notary_address].pool_index)


# Update notary_sample_size
@public
def update_notary_sample_size() -> bool:
    current_period: int128 = floor(block.number / self.PERIOD_LENGTH)
    if self.notary_sample_size_updated_period >= current_period:
        return False

    self.current_period_notary_sample_size = self.next_period_notary_sample_size
    self.notary_sample_size_updated_period = current_period

    return True


# Adds an entry to notary_registry, updates the notary pool (notary_pool, notary_pool_len, etc.),
# locks a deposit of size NOTARY_DEPOSIT, and returns True on success.
@public
@payable
def register_notary() -> bool:
    assert msg.value >= self.NOTARY_DEPOSIT
    assert not self.does_notary_exist[msg.sender]

    # Update notary_sample_size
    self.update_notary_sample_size()

    # Add the notary to the notary pool
    pool_index: int128 = self.notary_pool_len
    if not self.is_empty_slots_stack_empty():
        pool_index = self.empty_slots_stack_pop()        
    self.notary_pool[pool_index] = msg.sender
    self.notary_pool_len += 1

    # If index is larger than notary_sample_size, expand notary_sample_size in next period.
    if pool_index >= self.next_period_notary_sample_size:
        self.next_period_notary_sample_size = pool_index + 1

    # Add the notary to the notary registry
    self.notary_registry[msg.sender] = {
        deregistered: 0,
        pool_index: pool_index,
    }
    self.does_notary_exist[msg.sender] = True

    log.RegisterNotary(pool_index, msg.sender)

    return True


# Sets the deregistered period in the notary_registry entry, updates the notary pool (notary_pool, notary_pool_len, etc.),
# and returns True on success.
@public
def deregister_notary() -> bool:
    assert self.does_notary_exist[msg.sender] == True

    # Update notary_sample_size
    self.update_notary_sample_size()

    # Delete entry in notary pool
    index_in_notary_pool: int128 = self.notary_registry[msg.sender].pool_index 
    self.empty_slots_stack_push(index_in_notary_pool)
    self.notary_pool[index_in_notary_pool] = None
    self.notary_pool_len -= 1

    # Set deregistered period to current period
    self.notary_registry[msg.sender].deregistered = floor(block.number / self.PERIOD_LENGTH)

    log.DeregisterNotary(index_in_notary_pool, msg.sender, self.notary_registry[msg.sender].deregistered)

    return True


# Removes an entry from notary_registry, releases the notary deposit, and returns True on success.
@public
def release_notary() -> bool:
    assert self.does_notary_exist[msg.sender] == True
    assert self.notary_registry[msg.sender].deregistered != 0
    assert floor(block.number / self.PERIOD_LENGTH) > self.notary_registry[msg.sender].deregistered + self.NOTARY_LOCKUP_LENGTH

    pool_index: int128 = self.notary_registry[msg.sender].pool_index
    # Delete entry in notary registry
    self.notary_registry[msg.sender] = {
        deregistered: 0,
        pool_index: 0,
    }
    self.does_notary_exist[msg.sender] = False

    send(msg.sender, self.NOTARY_DEPOSIT)

    log.ReleaseNotary(pool_index, msg.sender)

    return True


# Given shard_id and index, return the chosen notary in the current period
@public
@constant
def get_member_of_committee(
        shard_id: int128,
        index: int128,
    ) -> address:
    period: int128 = floor(block.number / self.PERIOD_LENGTH)

    # Decide notary pool length based on if notary sample size is updated
    sample_size: int128
    if self.notary_sample_size_updated_period < period:
        sample_size = self.next_period_notary_sample_size
    elif self.notary_sample_size_updated_period == period:
        sample_size = self.current_period_notary_sample_size

    # Block hash used as entropy is the latest block of previous period  
    entropy_block_number: int128 = period * self.PERIOD_LENGTH - 1

    sampled_index: int128 = convert(
        uint256_mod(
            convert(
                sha3(
                    concat(
                        blockhash(entropy_block_number),
                        convert(shard_id, "bytes32"),
                        convert(index, "bytes32"),
                    )
                ),
                "uint256",
            ),
            convert(sample_size, "uint256"),
        ),
        'int128',
    )
    return self.notary_pool[sampled_index]


# Helper function to get collation header score
@public
@constant
def get_collation_header_score(shard_id: int128, collation_header_hash: bytes32) -> int128:
    collation_score: int128 = convert(
        uint256_mod(
            convert(self.collation_headers[shard_id][collation_header_hash], 'uint256'),
            # Mod 2^48, i.e., extract right most 6 bytes
            convert(281474976710656, 'uint256')
        ),
        'int128'
    )
    return collation_score


# Attempts to process a collation header, returns True on success, reverts on failure.
@public
def add_header(
        shard_id: int128,
        expected_period_number: int128,
        period_start_prevhash: bytes32,
        parent_hash: bytes32,
        transaction_root: bytes32,
        collation_coinbase: address,  # TODO: cannot be named `coinbase` since it is reserved
        state_root: bytes32,
        receipt_root: bytes32,
        collation_number: int128) -> bool:  # TODO: cannot be named `number` since it is reserved

    # Check if the header is valid
    assert (shard_id >= 0) and (shard_id < self.SHARD_COUNT)
    assert block.number >= self.PERIOD_LENGTH
    assert expected_period_number == floor(block.number / self.PERIOD_LENGTH)
    assert period_start_prevhash == blockhash(expected_period_number * self.PERIOD_LENGTH - 1)
    # Check if only one collation in one period perd shard
    assert self.period_head[shard_id] < expected_period_number

    # Update notary_sample_size
    self.update_notary_sample_size()

    # Check if this header already exists
    header_bytes: bytes <= 288 = concat(
        convert(shard_id, 'bytes32'),
        convert(expected_period_number, 'bytes32'),
        period_start_prevhash,
        parent_hash,
        transaction_root,
        convert(collation_coinbase, 'bytes32'),
        state_root,
        receipt_root,
        convert(collation_number, 'bytes32'),
    )
    entire_header_hash: bytes32 = convert(
        uint256_mod(
            convert(sha3(header_bytes), 'uint256'),
            # Mod 2^208, i.e., extract right most 26 bytes
            convert(411376139330301510538742295639337626245683966408394965837152256, 'uint256')
        ),
        'bytes32'
    )
    
    # Check if parent header exists.
    # If it exist, check that it's score is greater than 0.
    parent_collation_score: int128 = self.get_collation_header_score(
        shard_id,
        parent_hash,
    )
    if not not parent_hash:
        assert parent_collation_score > 0

    # Check score == collation_number
    _score: int128 = parent_collation_score + 1
    assert collation_number == _score

    # Add the header
    self.collation_headers[shard_id][entire_header_hash] = convert(
        uint256_add(
            uint256_mul(
                convert(parent_hash, 'uint256'),
                # Multiplied by 2^48, i.e., left shift 6 bytes
                convert(281474976710656, 'uint256')
            ),
            uint256_mod(
                convert(_score, 'uint256'),
                # Mod 2^48, i.e. confine it's range to 6 bytes
                convert(281474976710656, 'uint256')
            ),
        ),
        'bytes32'
    )

    # Update the latest period number
    self.period_head[shard_id] = expected_period_number

    # Determine the head
    is_new_head: bool = False
    shard_head_score: int128 = self.get_collation_header_score(
        shard_id,
        self.shard_head[shard_id],
    )
    if _score > shard_head_score:
        self.shard_head[shard_id] = entire_header_hash
        is_new_head = True

    # Emit log
    log.CollationAdded(
        shard_id,
        expected_period_number,
        period_start_prevhash,
        parent_hash,
        transaction_root,
        collation_coinbase,
        state_root,
        receipt_root,
        collation_number,
        is_new_head,
        _score,
    )

    return True