### Preliminaries

We assume that at address `VALIDATOR_MANAGER_ADDRESS` (on the existing "main shard") there exists a contract that manages an active "validator set", and supports the following functions:

-   `deposit(address validationCodeAddr, address returnAddr) returns uint256`: adds a validator to the validator set, with the validator's size being the `msg.value` (ie. amount of ETH deposited) in the function call. Returns the validator index. `validationCodeAddr` stores the address of the validation code; the function fails if this address's code has not been purity-verified.
-   `withdraw(uint256 validatorIndex, bytes sig) returns bool`: verifies that the signature is correct (ie. a call with 200000 gas, `validationCodeAddr` as destination, 0 value and `sha3("withdraw") + sig` as data returns 1), and if it is removes the validator from the validator set and refunds the deposited ETH.
-   `sample(uint256 shardId) returns uint256`: uses a recent block hash as a seed to pseudorandomly select a signer from the validator set. Chance of being selected should be proportional to the validator's deposit.
-   `addHeader(bytes header) returns bool`: attempts to process a collation header, returns True on success, reverts on failure.
-   `getShardHead(uint256 shardId) returns bytes32`: returns the header hash that is the head of a given shard as perceived by the manager contract.
-   `getAncestor(bytes32 hash)`: returns the 10000th ancestor of this hash.
-   `getAncestorDistance(bytes32 hash)`: returns the difference between the block number of this hash and the block number of the 10000th ancestor of this hash.
-   `getCollationGasLimit()`: returns the gas limit that collations can currently have (by default make this function always answer 10 million).
-   `txToShard(address to, uint256 shardId, uint256 tx_startgas, uint256 tx_gasprice, bytes data) returns uint256`: records a request to deposit `msg.value` ETH to address `to` in shard `shardId` during a future collation, with `startgas=tx_gasprice` and `gasprice=tx_gasprice`.  Saves a receipt ID for this request, also saving `msg.value`, `to`, `shardId`, `tx_startgas`, `tx_gasprice`, `data` and `msg.sender`.
-   `update_gasprice(uint256 receipt_id, uint256 tx_gasprice) returns bool`: updates the `tx_gasprice` in receipt `receipt_id`, and returns True on success.

### Parameters

-   `SERENITY_FORK_BLKNUM`: ????
-   `SHARD_COUNT`: 100
-   `VALIDATOR_MANAGER_ADDRESS`: ????
-   `USED_RECEIPT_STORE_ADDRESS`: ????
-   `SIG_GASLIMIT`: 40000
-   `COLLATOR_REWARD`: 0.002
-   `PERIOD_LENGTH`: 5 blocks
-   `SHUFFLING_CYCLE`: 2500 blocks

### Specification

We first define a "collation header" as an RLP list with the following values:

    [
        shard_id: uint256,
        expected_period_number: uint256,
        period_start_prevhash: bytes32,
        parent_collation_hash: bytes32,
        tx_list_root: bytes32,
        coinbase: address,
        post_state_root: bytes32,
        receipts_root: bytes32,
        sig: bytes
    ]

Where:

-   `shard_id` is the shard ID of the shard
-   `expected_period_number` is the period number in which this collation expects to be included. A period is an interval of `PERIOD_LENGTH` blocks.
-   `period_start_prevhash` is the block hash of block `PERIOD_LENGTH * expected_period_number - 1` (ie. the last block before the expected period starts). Opcodes in the shard that refer to block data (eg. NUMBER, DIFFICULTY) will refer to the data of this block, with the exception of COINBASE, which will refer to the shard coinbase.
-   `parent_collation_hash` is the hash of the parent collation
-   `tx_list_root` is the root hash of the trie holding the transactions included in this collation
-   `post_state_root` is the new state root of the shard after this collation
-   `receipts_root` is the root hash of the receipt trie
-   `sig` is a signature

For blocks where `block.number >= SERENITY_FORK_BLKNUM`, the block header's extra data must contain a hash which points to an RLP list of `SHARD_COUNT` objects, where each object is either the empty string or a valid collation header for a shard.

A **collation header** is valid if calling `addHeader(header)` returns true. The validator manager contract should do this if:

-   The `shard_id` is at least 0, and less than `SHARD_COUNT`
-   The `expected_period_number` equals `floor(block.number / PERIOD_LENGTH)`
-   A collation with the hash `parent_collation_hash` has already been accepted
-   The `sig` is a valid signature. That is, if we calculate `validation_code_addr = sample(shard_id)`, then call `validation_code_addr` with the calldata being `sha3(shortened_header) ++ sig` (where `shortened_header` is the RLP encoded form of the collation header _without_ the sig), the result of the call should be 1

A **collation** is valid if (i) its collation header is valid, (ii) executing the collation on top of the `parent_collation_hash`'s `post_state_root` results in the given `post_state_root` and `receipts_root`, and (iii) the total gas used is less than or equal to the output of calling `getCollationGasLimit()` on the main shard.

### Collation state transition function

The state transition process for executing a collation is as follows:

* Execute each transaction in the tree pointed to by `tx_list_root` in order
* Assign a reward of `COLLATOR_REWARD` to the coinbase

### Receipt-consuming transactions

A transaction in a shard can use a receipt ID as its signature (that is, (v, r, s) = (1, receiptID, 0)). Let `(to, value, shard_id, tx_startgas, tx_gasprice, sender, data)` be the values that were saved by the `txToShard` call that created this receipt. For such a transaction to be valid:

* Such a receipt *must* have in fact been created by a `txToShard` call in the main chain.
* The `to`, `value`, `startgas`, and `gasprice` of the transaction *must* match the `to`, `value`, `tx_startgas` and `tx_gasprice` of this receipt.
* The shard Id *must* match `shard_id`.
* The contract at address `USED_RECEIPT_STORE_ADDRESS` *must NOT* have a record saved saying that the given receipt ID was already consumed.

The transaction has an additional side effect of saving a record in `USED_RECEIPT_STORE_ADDRESS` saying that the given receipt ID has been consumed. Such a transaction effects a message whose:

* `sender` is `USED_RECEIPT_STORE_ADDRESS`
* `to` is the `to` from the receipt
* `startgas` is the `tx_startgas` from the receipt
* `gasprice` is the `tx_gasprice` from the receipt
* `value` is the `value` from the receipt, minus `gasprice * gaslimit`
* `data` is twelve zero bytes concatenated with the `sender` from the receipt concatenated with the `data` from the receipt
* Gas refunds go to the `to` address

### Details of `sample`

The `sample` function should be coded in such a way that any given validator randomly gets allocated to some number of shards every `SHUFFLING_CYCLE`, where the expected number of shards is proportional to the validator's balance. During that cycle, `sample(shard_id)` can only return that validator if the `shard_id` is one of the shards that they were assigned to. The purpose of this is to give validators time to download the state of the specific shards that they are allocated to.

Here is one possible implementation of `sample`, assuming for simplicity of illustration that all validators have the same deposit size:

    def sample(shard_id: num) -> address:
        cycle = floor(block.number / SHUFFLING_CYCLE)
        cycle_seed = blockhash(cycle * SHUFFLING_CYCLE)
        seed = blockhash(block.number - (block.number % PERIOD_LENGTH))
        index_in_subset = num256_mod(as_num256(sha3(concat(seed, as_bytes32(shard_id)))),
                                     100)
        validator_index = num256_mod(as_num256(sha3(concat(cycle_seed), as_bytes32(shard_id), as_bytes32(index_in_subset))),
                                     as_num256(self.validator_set_size))
        return self.validators[validator_index]

This picks out 100 validators for each shard during each cycle, and then during each block one out of those 100 validators is picked by choosing a distinct `index_in_subset` for each block.

### Collation Header Production and Propagation

We generally expect collation headers to be produced and propagated as follows.

* Every time a new `SHUFFLING_CYCLE` starts, every validator computes the set of 100 validators for every shard that they were assigned to, and sees which shards they are eligible to validate in. The validator then downloads the state for that shard (using fast sync)
* The validator keeps track of the head of the chain for all shards they are currently assigned to. It is each validator's responsibility to reject invalid or unavailable collations, and refuse to build on such blocks, even if those blocks get accepted by the main chain validator manager contract.
* If a validator is currently eligible to validate in some shard `i`, they download the full collation association with any collation header that is included into block headers for shard `i`.
* When on the current global main chain a new period starts, the validator calls `sample(i)` to determine if they are eligible to create a collation; if they are, then they do so.

### Rationale

This allows for a quick and dirty form of medium-security proof of stake sharding in a way that achieves quadratic scaling through separation of concerns between block proposers and collators, and thereby increases throughput by ~100x without too many changes to the protocol or software architecture. This is intended to serve as the first phase in a multi-phase plan to fully roll out quadratic sharding, the latter phases of which are described below.

### Subsequent phases

* **Phase 2, option a**: require collation headers to be added in as uncles instead of as transactions
* **Phase 2, option b**: require collation headers to be added in an array, where item `i` in the array must be either a collation header of shard `i` or the empty string, and where the extra data must be the hash of this array (soft fork)
* **Phase 3 (two-way pegging)**: add to the `USED_RECEIPT_STORE_ADDRESS` contract a function that allows receipts to be created in shards. Add to the main chain's `VALIDATOR_MANAGER_ADDRESS` a function for submitting Merkle proofs of unspent receipts that have confirmed (ie. they point to some hash `h` such that some hash `h2` exists such that `getAncestor(h2) = h` and `getAncestorDistance(h2) < 10000 * PERIOD_LENGTH * 1.33`), which has similar behavior to the `USED_RECEIPT_STORE_ADDRESS` contract in the shards.
* **Phase 4 (tight coupling)**: blocks are no longer valid if they point to invalid or unavailable collations. Add data availability proofs.
