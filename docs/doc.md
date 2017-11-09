### Preliminaries

We assume that at address `VALIDATOR_MANAGER_ADDRESS` (on the existing "main shard") there exists a contract that manages an active "validator set", and supports the following functions:

-   `deposit(address validationCodeAddr, address returnAddr) returns uint256`: adds a validator to the validator set, with the validator's size being the `msg.value` (ie. amount of ETH deposited) in the function call. Returns the validator index. `validationCodeAddr` stores the address of the validation code; the function fails if this address's code has not been purity-verified.
-   `withdraw(uint256 validatorIndex, bytes sig) returns bool`: verifies that the signature is correct (ie. a call with 200000 gas, `validationCodeAddr` as destination, 0 value and `sha3("withdraw") + sig` as data returns 1), and if it is removes the validator from the validator set and refunds the deposited ETH.
-   `getEligibleProposer(uint256 shardId, uint256 period) returns uint256`: uses a block hash as a seed to pseudorandomly select a signer from the validator set. Chance of being selected should be proportional to the validator's deposit. Should be able to return a value for the current period or any future period up to `LOOKAHEAD_PERIODS` periods ahead.
-   `addHeader(bytes header) returns bool`: attempts to process a collation header, returns True on success, reverts on failure.
-   `getShardHead(uint256 shardId) returns bytes32`: returns the header hash that is the head of a given shard as perceived by the manager contract.
-   `getAncestor(bytes32 hash)`: returns the 10000th ancestor of this hash.
-   `getAncestorDistance(bytes32 hash)`: returns the difference between the block number of this hash and the block number of the 10000th ancestor of this hash.
-   `getCollationGasLimit()`: returns the gas limit that collations can currently have (by default make this function always answer 10 million).
-   `txToShard(address to, uint256 shardId, uint256 tx_startgas, uint256 tx_gasprice, bytes data) returns uint256`: records a request to deposit `msg.value` ETH to address `to` in shard `shardId` during a future collation, with `startgas=tx_startgas` and `gasprice=tx_gasprice`.  Saves a receipt ID for this request, also saving `msg.value`, `to`, `shardId`, `tx_startgas`, `tx_gasprice`, `data` and `msg.sender`.
-   `update_gasprice(uint256 receipt_id, uint256 tx_gasprice) returns bool`: updates the `tx_gasprice` in receipt `receipt_id`, and returns True on success.

There are also the following public variables:

* `collations: ({parent: bytes32, score: uint256...})[bytes32]` - this implicitly serves as a "hash to collation header" lookup, as well as giving the parent of a collation and the score (ie. depth in the collation tree) of a collation
* `num_collations_with_score: num[num]` - gives the number of collations that have the given score
* `collations_with_score: bytes32[num][num]` - `[i][j]` gives the jth collation with score i.

### Parameters

-   `SERENITY_FORK_BLKNUM`: ????
-   `SHARD_COUNT`: 100
-   `VALIDATOR_MANAGER_ADDRESS`: ????
-   `USED_RECEIPT_STORE_ADDRESS`: ????
-   `SIG_GASLIMIT`: 40000
-   `COLLATOR_REWARD`: 0.001
-   `PERIOD_LENGTH`: 5 blocks
-   `LOOKAHEAD_PERIODS`: 3
-   `SHUFFLING_CYCLE_LENGTH`: 2500 blocks

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

### Details of `getEligibleProposer`

Here is one simple implementation in Viper:

```python
def getEligibleProposer(shardId: num, period: num) -> num:
    assert period * PERIOD_LENGTH < block.number + 20
    h = as_num256(blockhash(period * PERIOD_LENGTH - 20))
    return as_num128(num256_mod(h, as_num256(self.validator_count)))
```

### Client Logic

A client would have a config of the following form:

```python
{
    validator_address: "0x..." OR null,
    watching: [list of shard ids],
    ...
}
```

If a validator address is provided, then it checks if the address is an active validator. If it does, then every time a new period on the main chain starts (ie. when `block.number // PERIOD_LENGTH` changes), then it should call `getEligibleProposer` for all shards for period `block.number // PERIOD_LENGTH + LOOKAHEAD_PERIODS`. If it returns the validator's address for some shard `i`, then it runs the algorithm `MAKE_BLOCK(i)` (see below).

For every shard `i` in the `watching` list, every time a new collation header appears in the main chain, it downloads the full collation from the shard network, and verifies it. It locally keeps track of all valid headers (where validity is defined recursively, ie. for a header to be valid its parent must also be valid), and repeatedly runs the algorithm `GET_HEAD(i)` (see below).

### GET_HEAD

Pseudocode here:
```python
h = validator_manager_contract.getShardHead(i)
if h in self.validHeaders:
    return h
s = validator_manager_contract.getScore(h)
while 1:
    n = validator_manager_contract.get_num_collations_with_score(s)
    for i in range(n):
        h = validator_manager_contract.get_collations_with_score(s, i)
        if h in self.validHeaders:
            return h
    s -= 1
```

Basically, see if the head provided by the `validator_manager_contract` is valid first, and if not, then walk down checking collation headers with progressively lower scores until you find one that is; accept that one.

### MAKE_BLOCK

This process has three parts. The first part can be called `GUESS_HEAD(s)`, with pseudocode here:

```python
def main():
    cur_head_guess = validator_manager_contract.get_head()
    depth = 4
    while 1:
        all_collations = get_collations_with_scores_in_range(low=cur_head_guess - depth, high=cur_head_guess.score)
        best_collation_hash = 0
        best_collation_score = 0
        for collation in all_collations:
            c = collation
            collation_is_valid = True
            while c.score >= depth - cur_head_guess:
                if not full_validate(c):
                    collation_is_valid = False
                    break
                c = validator_manager_contract.get_parent(c)
            if collation_is_valid:
                if c.score > best_collation_score:
                    best_collation_hash = c.hash
                    best_collation_score = c.score
        cur_head_guess = best_collation_hash
        depth *= 2

def get_collations_with_scores_in_range(low, high):
    o = []
    for i in range(low, high+1):
        o.extend(get_collations_with_score(i))
    return o

def get_collations_with_score(score):
    return [validator_manager_contract.get_collations_with_score(score, i) for i in
            range(validator_manager_contract.get_num_collations_with_score(score))]

```

`full_validate(c)` involves fetching the full data of `c` (including witnesses) from the shard network, and verifying it. Note that `full_validate` and `get_collations_with_score` can both be memoized to avoid redoing computation. The above algorithm is equivalent to "pick the longest valid chain, but only check validity for the most recent N collations" where N starts at 4 and grows over time. The algorithm should only stop when the validator runs out of time and it is time to create the collation. Every execution of `full_validate` should also return a "write set". Save all of these write sets, and combine them together; this is the `recent_trie_nodes_db`.

We then define `UPDATE_WITNESS(tx, recent_trie_nodes_db)`. While running `GUESS_HEAD`, a node will have received some transactions. When it comes time to (attempt to) include a transaction into a collation, this algorithm will need to be run on the transaction first. Suppose that the transaction has an address list `[A1 ... An]`, and a witness `W`. For each `Ai`, use the current state tree root and get the Merkle branch for `Ai`, using the union of `recent_trie_nodes_db` and `W` as a database. If the original `W` was correct, and the transaction was sent not before the time that the client checked back to, then getting this Merkle branch will always succeed. After including the transaction into a collation, the "write set" from the state change should then also be added into the `recent_trie_nodes_db`.

For illustration, here is full pseudocode for the transaction-getting part of `CREATE_COLLATION`:

```python
# Sort by descending order of gasprice
txpool = sorted(copy(available_transactions), key=-tx.gasprice)
collation = new Collation(...)
while len(txpool) > 0:
    # Remove txs that ask for too much gas
    i = 0
    while i < len(txpool):
        if txpool[i].startgas > GASLIMIT - block.gasused:
            txpool.pop(i)
        else:
            i += 1
    tx.witness = UPDATE_WITNESS(tx.witness, recent_trie_nodes_db)
    # Try to add the transaction, discard if it fails
    success, reads, writes = add_transaction(collation, txpool[0])
    recent_trie_nodes_db = union(recent_trie_nodes_db, writes)
    txpool.pop(0)
```

At the end, there is an additional step, finalizing the collation (to give the collator the reward, which is `COLLATOR_REWARD` ETH). This requires asking the network for a Merkle branch for the collator's account. When the network replies with this, the post-state root after applying the reward, as well as the fees, can be calculated. The collator can then package up the collation, of the form (header, txs, witness), where the witness is the union of the witnesses of all the transactions and the branch for the collator's account.

### Rationale

This allows for a quick and dirty form of medium-security proof of stake sharding in a way that achieves quadratic scaling through separation of concerns between block proposers and collators, and thereby increases throughput by ~100x without too many changes to the protocol or software architecture. This is intended to serve as the first phase in a multi-phase plan to fully roll out quadratic sharding, the latter phases of which are described below.

### Subsequent phases

* **Phase 2, option a**: require collation headers to be added in as uncles instead of as transactions
* **Phase 2, option b**: require collation headers to be added in an array, where item `i` in the array must be either a collation header of shard `i` or the empty string, and where the extra data must be the hash of this array (soft fork)
* **Phase 3 (two-way pegging)**: add to the `USED_RECEIPT_STORE_ADDRESS` contract a function that allows receipts to be created in shards. Add to the main chain's `VALIDATOR_MANAGER_ADDRESS` a function for submitting Merkle proofs of unspent receipts that have confirmed (ie. they point to some hash `h` such that some hash `h2` exists such that `getAncestor(h2) = h` and `getAncestorDistance(h2) < 10000 * PERIOD_LENGTH * 1.33`), which has similar behavior to the `USED_RECEIPT_STORE_ADDRESS` contract in the shards.
* **Phase 4 (tight coupling)**: blocks are no longer valid if they point to invalid or unavailable collations. Add data availability proofs.
