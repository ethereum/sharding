# NOTE: Some variables are set as public variables for testing. They should be reset
# to private variables in an official deployment of the contract. 

#
# Events
#

RegisterNotary: event({index_in_notary_pool: int128, notary: indexed(address)})
DeregisterNotary: event({index_in_notary_pool: int128, notary: indexed(address), deregistered_period: int128})
ReleaseNotary: event({index_in_notary_pool: int128, notary: indexed(address)})
AddHeader: event({period: int128, shard_id: indexed(int128), chunk_root: bytes32})
SubmitVote: event({period: int128, shard_id: indexed(int128), chunk_root: bytes32, notary: address})


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
# - deposit: notary's deposit value
notary_registry: {
    deregistered: int128,
    pool_index: int128,
    deposit: wei_value
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

# Collation
# - collation_records: the collation records that have been appended by the proposer.
# Mapping [period][shard_id] to chunk_root and proposer. is_elected is used to indicate if
# this collation has received enough votes.
# - records_updated_period: the latest period in which new collation header has been
# submitted for the given shard.
# - head_collation_period: period number of the head collation in the given shard, e.g., if
# a collation which is added in period P in shard 3 receives enough votes, then
# head_collation_period[3] is set to P.
collation_records: public({
    chunk_root: bytes32,
    proposer: address,
    is_elected: bool
}[int128][int128])
records_updated_period: public(int128[int128])
head_collation_period: public(int128[int128])

# Notarization
# - current_vote: vote count of collation in current period in each shard.
# First 31 bytes: bitfield of which notary has voted and which has not. First bit
# represents notary's vote(notary with index 0 in get_committee_member) and second
# bit represents next notary's vote(notary with index 1) and so on.
current_vote: public(bytes32[int128])


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
        deposit: msg.value,
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
    deposit: wei_value = self.notary_registry[msg.sender].deposit
    # Delete entry in notary registry
    self.notary_registry[msg.sender] = {
        deregistered: 0,
        pool_index: 0,
        deposit: 0,
    }
    self.does_notary_exist[msg.sender] = False

    send(msg.sender, deposit)

    log.ReleaseNotary(pool_index, msg.sender)

    return True


# Given shard_id and index, return the chosen notary in the current period
@public
@constant
def get_member_of_committee(
        shard_id: int128,
        index: int128,
    ) -> address:
    # Check that shard_id is valid
    assert shard_id >= 0 and shard_id < self.SHARD_COUNT
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
        convert(
            sha3(
                concat(
                    blockhash(entropy_block_number),
                    convert(shard_id, "bytes32"),
                    convert(index, "bytes32"),
                )
            ),
            "uint256",
        ) % convert(sample_size, "uint256"),
        'int128',
    )
    return self.notary_pool[sampled_index]


# Attempts to process a collation header, returns True on success, reverts on failure.
@public
def add_header(
        shard_id: int128,
        period: int128,
        chunk_root: bytes32
    ) -> bool:

    # Check that shard_id is valid
    assert shard_id >= 0 and shard_id < self.SHARD_COUNT
    # Check that it's current period
    current_period: int128 = floor(block.number / self.PERIOD_LENGTH)
    assert current_period == period
    # Check that no header is added yet in this period in this shard
    assert self.records_updated_period[shard_id] < period

    # Update notary_sample_size
    self.update_notary_sample_size()

    # Add header
    self.collation_records[shard_id][period] = {
        chunk_root: chunk_root,
        proposer: msg.sender,
        is_elected: False,
    }

    # Update records_updated_period
    self.records_updated_period[shard_id] = current_period

    # Clear previous vote count
    self.current_vote[shard_id] = None

    # Emit log
    log.AddHeader(
        period,
        shard_id,
        chunk_root,
    )

    return True


# Helper function to get vote count
@public
@constant
def get_vote_count(shard_id: int128) -> int128:
    current_vote_in_uint: uint256 = convert(self.current_vote[shard_id], 'uint256')

    # Extract current vote count(last byte of current_vote)
    return convert(
        current_vote_in_uint % convert(
            2**8,
            'uint256'
        ),
        'int128'
    )


# Helper function to get vote count
@public
@constant
def has_notary_voted(shard_id: int128, index: int128) -> bool:
    # Right shift current_vote then AND(bitwise) it's value with value 1 to see if
    # notary of given index in bitfield had voted.
    current_vote_in_uint: uint256 = convert(self.current_vote[shard_id], 'uint256')
    # Convert the result from integer to bool
    return not not bitwise_and(
        current_vote_in_uint,
        shift(convert(1, 'uint256'), 255 - index),
    )


@private
def update_vote(shard_id: int128, index: int128) -> bool:
    current_vote_in_uint: uint256 = convert(self.current_vote[shard_id], 'uint256')
    index_in_bitfield: uint256 = shift(convert(1, 'uint256'), 255 - index)
    old_vote_count: int128 = self.get_vote_count(shard_id)

    # Update bitfield
    current_vote_in_uint = bitwise_or(current_vote_in_uint, index_in_bitfield)
    # Update vote count
    # Add an upper bound check to prevent 1-byte vote count overflow
    if old_vote_count < 255:
        current_vote_in_uint = current_vote_in_uint + convert(1, 'uint256')
    self.current_vote[shard_id] = convert(current_vote_in_uint, 'bytes32')

    return True


# Notary submit a vote
@public
def submit_vote(
        shard_id: int128,
        period: int128,
        chunk_root: bytes32,
        index: int128,
    ) -> bool:

    # Check that shard_id is valid
    assert shard_id >= 0 and shard_id < self.SHARD_COUNT
    # Check that it's current period
    current_period: int128 = floor(block.number / self.PERIOD_LENGTH)
    assert current_period == period
    # Check that index is valid
    assert index >= 0 and index < self.COMMITTEE_SIZE
    # Check that notary is eligible to cast a vote
    assert self.get_member_of_committee(shard_id, index) == msg.sender
    # Check that collation record exists and matches
    assert self.records_updated_period[shard_id] == period
    assert self.collation_records[shard_id][period].chunk_root == chunk_root
    # Check that notary has not yet voted
    assert not self.has_notary_voted(shard_id, index)

    # Update bitfield and vote count
    assert self.update_vote(shard_id, index)

    # Check if we have enough vote and make update accordingly
    current_vote_count: int128 = self.get_vote_count(shard_id)
    if current_vote_count >= self.QUORUM_SIZE and \
        not self.collation_records[shard_id][period].is_elected:
        self.head_collation_period[shard_id] = period
        self.collation_records[shard_id][period].is_elected = True

    # Emit log
    log.SubmitVote(
        period,
        shard_id,
        chunk_root,
        msg.sender,
    )

    return True
