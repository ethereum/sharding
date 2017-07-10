### Preliminaries

We assume that at address `VALIDATOR_MANAGER_ADDRESS` (on the existing "main shard") there exists a contract that manages an active "validator set", and supports the following functions:

-   `deposit(address validationCodeAddr, address returnAddr) returns uint256`: adds a validator to the validator set, with the validator's size being the `msg.value` (ie. amount of ETH deposited) in the function call. Returns the validator index. `validationCodeAddr` stores the address of the validation code; the function fails if this address's code has not been purity-verified.
-   `withdraw(uint256 validatorIndex, bytes sig) returns bool`: verifies that the signature is correct (ie. a call with 200000 gas, `validationCodeAddr` as destination, 0 value and `sha3("withdraw") + sig` as data returns 1).
-   `sample(uint256 block_number, uint256 shardId, uint256 sigIndex) returns uint256`: uses the block hash of the given block number as a seed to pseudorandomly select a signer from the validator set. Chance of being selected should be proportional to the validator's deposit.

### Parameters

-   `SERENITY_FORK_BLKNUM`: ????
-   `MAX_SHARD_DEPTH`: 4
-   `SHARD_CHILD_COUNT`: 3
-   `SIGNATURE_COUNT`: 12
-   `VALIDATOR_MANAGER_ADDRESS`: ????
-   `SIG_GASLIMIT`: 200000
-   `ROOT_SHARD_SIGNER_REWARD`: 0.002
-   `SHARD_REWARD_DECAY_FACTOR`: 3
-   `SHUFFLING_CYCLE`: 2500 blocks

### Specification

We first define a "collation header" as an RLP list with the following
values:

    [
        shardId: uint256,
        parent_block_number: uint256,
        parent_block_hash: bytes32,
        rng_source_block_number: uint256,
        prev_state_root: bytes32,
        tx_list_root: bytes32,
        coinbase: address,
        post_state_root: bytes32,
        receipt_root: bytes32,
        children: [
            child1_hash: bytes32,
            ...
            child[SHARD_CHILD_COUNT]hash: bytes32
        ],
        state_branch_node: bytes32,
        signatures: [
            sig1: bytes,
            ...
            sig[SIGNATURE_COUNT]: bytes
        ]
    ]

Where:

-   `shardId` is the shard ID of the shard
-   `parent_block_number` is the block number of the `parent_block_hash`
-   `parent_block_hash` is the block in which the previous collation header of this shard was included
-   `rng_source_block_number` is a block number equal to or greater than `parent_block_number`
-   `prev_state_root` is the previous state root of the shard
-   `tx_list_root` is the root hash of the trie holding the transactions included in this shard block
-   `post_state_root` is the new state root of the shard
-   `receipt_root` is the root hash of the receipt trie -   `children` is a list of hashes of collation headers for child shards of this shard (a child of shard `i` has children with IDs `i * SHARD_CHILD_COUNT + 1 ... (i+1) * SHARD_CHILD_COUNT`). Each hash can also be the hash of the empty string if no collation header for that child is present
-   `state_branch_node` is the sha3 of the `post_state_root` concatenated with the `state_branch_node` values for each child (ie.  `sha3(post_state_root ++ child1.state_branch_node ++ .. ++ childn.state_branch_node)`).  If the depth of a shard is equal to `MAX_SHARD_DEPTH` (a shard has depth 0 if it has no parents, otherwise the depth is 1 plus the depth of its parent), then this list MUST have length 0.
-   `signatures` is a list of items each of which is either empty or a signature

For blocks where `block.number >= SERENITY_FORK_BLKNUM`, the block header's extra data must be either a *locally valid* collation header for shard 0 or the empty string. We define the "current state branch root" as being the `state_branch_node` of shard 0 for the most recent block that had a collation header, the "current state branch node" of any shard as being the state branch node that is in the tree whose root is the state branch root, and the "current state root" of any shard as being the state root that is in the tree whose root is the state branch root.

If there has not yet been a collation header, then we assume the current state root of a shard is the genesis state root of that shard (this is a protocol parameter), and we can use this to derive the starting state branch nodes for every shard, including the starting state root.

We define a collation header as "locally valid" if:

-   The `parent_block_number` actually is the block number in which the previous collation header for the given shard was included
-   The `parent_block_hash` actually is the hash of the block in which the previous collation header for the given shard was included
-   The `rng_source_block_number` is greater than or equal to `parent_block_number`
-   The `prev_state_root` is the current state root for the given shard
-   The `tx_list_root` points to a set of transactions that is valid and available
-   The `post_state_root` is the resulting state root of executing the transactions referenced by the `tx_list_root` on top of the `prev_state_root`
-   The `receipt_root` is the receipt root generated by the execution
-   If `shardId >= 1 + SHARD_CHILD_COUNT + ... + SHARD_CHILD_COUNT ** (MAX_SHARD_DEPTH-1)`, then the children is an empty list
-   If `shardId < 1 + SHARD_CHILD_COUNT + ... + SHARD_CHILD_COUNT ** (MAX_SHARD_DEPTH-1)`, then each entry in the children list is either an empty string, or a hash whose preimage is available, and whose `shardId` is this header's `shardId` multiplied by `SHARD_CHILD_COUNT` plus (1 + the child's index in the list)
-   The `state_branch_node` is the hash of the `post_state_root` together with the `state_branch_node` of each child; if a given child is empty then we take the current state branch node of that shard.
-   For all `0 <= sigIndex < SIGNATURE_COUNT`, let `validationCodeAddr` be the result of calling `sample(rng_source_block_number, shardId, sigIndex)`. A signature is "valid" if calling `validationCodeAddr` on the main shard with 200000 gas, 0 value, the mixhash concatenated with the sigIndex'th signature as input data gives output 1. All signatures must be valid or empty, and at least 3/4 of them must be valid.

### Details of `sample`

The `sample` function should be coded in such a way that any given validator randomly gets allocated to some number of shards every `SHUFFLING_CYCLE`, where the expected number of shards is proportional to the validator's balance. During that cycle, `sample(number, shardId, sigIndex)` can only return that validator if the `shardId` is one of the shards that they were assigned to. The purpose of this is to give validators time to download the state of the specific shards that they are allocated to.

Here is one possible implementation of `sample`, assuming for simplicity of illustration that all validators have the same deposit size:

    def sample(block_number: num, shardId: num, sigIndex: num) -> address:
        cycle = floor(block_number / 2500)
        cycle_seed = blockhash(cycle * 2500)
        seed = blockhash(block_number)
        index_in_subset = num256_mod(as_num256(sha3(concat(seed, as_bytes32(sigIndex)))),
                                     100)
        validator_index = num256_mod(as_num256(sha3(concat(cycle_seed), as_bytes32(shardId), as_bytes32(index_in_subset))),
                                     as_num256(self.validator_set_size))
        return self.validators[validator_index]

This picks out 100 validators for each shard during each cycle, and then during each block `SIGNATURE_COUNT` out of those 100 validators are picked by choosing the `index_in_subset` out of those 100 based on the block hash (`seed`) and the `sigIndex` which ranges from 0 to `SIGNATURE_COUNT - 1`.

### Shard Header Production and Propagation

We generally expect collation headers to be produced and propagated as follows.

* Every time a new `SHUFFLING_CYCLE` starts, every validator computes the set of 100 validators for every shard that they were assigned to, and sees which shards they are eligible to validate in. The validator then downloads the state for that shard (using fast sync)
* If a validator is currently eligible to validate in some shard `i`, they keep track of the "longest chain" of shard `i`. This is defined as the longest ordered collection of collation headers `c[1] ... c[n]` of shard `i` such that `c[i+1]` has the same `prev_state_root` as the `post_state_root` of `c[i]` and the `parent_block_hash` of `c[i+1]` is the hash of a block where `c[i]` was included, and where all `c[i]` were included in blocks in the current global main chain
* When a the current global main chain receives a new block:
    * The validator waits a few seconds to see if that block points to a new collation header of shard `i`; if so, they update their view of the shard chain.
    * Let H be the current head of the shard chain for shard `i`. The validator checks if they know of a collation header on top of H which has not yet been fully signed and included in a block. If there is, then they wait. If not, they call `sample(block_number, i, 0)` on the main chain and see if the call returns their address. If it does, then they create a new collation header on top of the current shard chain (referencing the most recent available fully signed collation headers of the child shards of `i` as children), sign it and broadcast it.
* If the validator receives a collation header on shard `i`, and this collation header is valid and on the head of the current main chain, they sign it and broadcast the signature.
* If a block maker sees a fully signed and valid header of shard 0, they include it in block extra data.

### Incentives

Currently, the coinbase of a block is rewarded with 5 ether, plus extra ether for uncle and nephew rewards, as part of the "block finalization function". Here, we also have a finalization function for each shard, though the logic is different: for every signer, increase the balance of the signer by `ROOT_SHARD_SIGNER_REWARD / SHARD_REWARD_DECAY_FACTOR ** shard_depth`. The signer in position 0 gets a reward `SIGNATURE_COUNT` times higher, to encourage validators in this special position to be more willing to propose blocks.

### Rationale

This allows for a quick and dirty form of medium-security proof of stake sharding in a way that achieves exponential scaling through separation of concerns between block proposers and collators, and thereby increases throughput by ~100x without too many changes to the protocol or software architecture. The intention would be to replace it in the next hardfork with a design that adds in erasure coded data availability proofs, fraud proofs, and the formal requirement for block proposers and validators to reject collations that are not valid at the transactional level, even if they have the requisite number of signatures.  Additionally, this model does not support movement of ETH between shards; it is the intention that the next hardfork after this will.

The shard tree structure ensures that no participant in the system needs to deal with more than `SHARD_CHILD_COUNT * SIGNATURE_COUNT` signatures; with 3 children and 12 signatures, multiplied by 200000 gas per signature, this gives an upper limit of 7.2 million gas, though in practice we expect many signatures to be much smaller than the maximum.
