### Introduction

The purpose of this document is to provide a reasonably complete specification and introduction for anyone looking to understand the details of the sharding proposal, as well as to implement it. This document as written describes only "phase 1" of quadratic sharding; phases 2, 3 and 4 are at this point out of scope, and super-quadratic sharding ("Ethereum 3.0") is also out of scope.

Suppose that the variable `c` denotes the level of computational power available to one node. In a simple blockchain, the transaction capacity is bounded by O(c), as every node must process every transaction. The goal of quadratic sharding is to increase the capacity with a two-layer design. Stage 1 requires no hard forks; the main chain stays exactly as is. However, a contract is published to the main chain called the **validator manager contract** (VMC), which maintains the sharding system. There are O(c) **shards** (currently, 100), where each shard is like a separate "galaxy": it has its own account space, transactions need to specify which shard they are to be published inside, and communication between shards is very limited (in fact, in phase 1, it is nonexistent).

The shards are run on a simple longest-chain-rule proof of stake system, where the stake is on the main chain (specifically, inside the VMC). All shards share a common validator pool; this also means that anyone who signs up with the VMC as a validator could theoretically at any time be assigned the right to create a block on any shard. Each shard has a block size/gas limit of O(c), and so the total capacity of the system is O(c^2).

Most users of the sharding system will run both (i) either a full (O(c)) or light (O(log(c))) node on the main chain, and (ii) a "shard client" which talks to the main chain node via RPC (assumed to be trusted because it's also running on the user's computer) and can be used as a light client for any shard, as a full client for any specific shard (the user would have to specify that they are "watching" a specific shard) or as a validator node. In all cases, the storage and computation requirements for a shard client will also not exceed O(c).

### Constants

* `LOOKAHEAD_PERIODS`: 4
* `PERIOD_LENGTH`: 5
* `COLLATION_GASLIMIT`: 10,000,000
* `SHARD_COUNT`: 100
* `SIG_GASLIMIT`: 40000
* `COLLATOR_REWARD`: 0.001

### The Validator Manager Contract

We assume that at address `VALIDATOR_MANAGER_ADDRESS` (on the existing "main shard") there exists the VMC, which supports the following functions:

-   `deposit(address validationCodeAddr, address returnAddr) returns uint256`: adds a validator to the validator set, with the validator's size being the `msg.value` (ie. amount of ETH deposited) in the function call. Returns the validator index. `validationCodeAddr` stores the address of the validation code, which is expected to store a pure function which expects as input a 32 byte hash followed by a signature, and returns 1 if the signature matches the hash and otherwise 0; the function fails if this address's code has not been purity-verified.
-   `withdraw(uint256 validatorIndex, bytes sig) returns bool`: verifies that the signature is correct (ie. a call with 200000 gas, `validationCodeAddr` as destination, 0 value and `sha3("withdraw") + sig` as data returns 1), and if it is removes the validator from the validator set and refunds the deposited ETH.
-   `getEligibleProposer(uint256 shardId, uint256 period) returns address`: uses a block hash as a seed to pseudorandomly select a signer from the validator set. Chance of being selected should be proportional to the validator's deposit. Should be able to return a value for the current period or any future period up to `LOOKAHEAD_PERIODS` periods ahead.
-   `addHeader(bytes header) returns bool`: attempts to process a collation header, returns True on success, reverts on failure.
-   `getShardHead(uint256 shardId) returns bytes32`: returns the header hash that is the head of a given shard as perceived by the manager contract.

There are also two log types:

-   `CollationAdded(indexed uint256 shard, bytes collationData, bool isNewHead)`

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
-   `expected_period_number` is the period number in which this collation expects to be included; this is calculated as `period_number = floor(block.number / PERIOD_LENGTH)`.
-   `period_start_prevhash` is the block hash of block `PERIOD_LENGTH * expected_period_number - 1` (ie. the last block before the expected period starts). Opcodes in the shard that refer to block data (eg. NUMBER, DIFFICULTY) will refer to the data of this block, with the exception of COINBASE, which will refer to the shard coinbase.
-   `parent_collation_hash` is the hash of the parent collation
-   `tx_list_root` is the root hash of the trie holding the transactions included in this collation
-   `post_state_root` is the new state root of the shard after this collation
-   `receipts_root` is the root hash of the receipt trie
-   `sig` is a signature

A **collation header** is valid if calling `addHeader(header)` returns true. The validator manager contract should do this if:

-   The `shard_id` is at least 0, and less than `SHARD_COUNT`
-   The `expected_period_number` equals the actual current period number (ie. `floor(block.number / PERIOD_LENGTH)`)
-   A collation with the hash `parent_collation_hash` for the same shard has already been accepted
-   The `sig` is a valid signature. That is, if we calculate `validation_code_addr = getEligibleProposer(shard_id, current_period)`, then call `validation_code_addr` with the calldata being `sha3(shortened_header) ++ sig` (where `shortened_header` is the RLP encoded form of the collation header _without_ the sig), the result of the call should be 1

A **collation** is valid if (i) its collation header is valid, (ii) executing the collation on top of the `parent_collation_hash`'s `post_state_root` results in the given `post_state_root` and `receipts_root`, and (iii) the total gas used is less than or equal to `COLLATION_GASLIMIT`.

### Collation state transition function

The state transition process for executing a collation is as follows:

* Execute each transaction in the tree pointed to by `tx_list_root` in order
* Assign a reward of `COLLATOR_REWARD` to the coinbase

### Details of `getEligibleProposer`

Here is one simple implementation in Viper:

```python
def getEligibleProposer(shardId: num, period: num) -> address:
    assert period >= LOOKAHEAD_PERIODS
    assert (period - LOOKAHEAD_PERIODS) * PERIOD_LENGTH < block.number
    assert self.num_validators > 0

    h = as_num256(
        sha3(
            concat(
                blockhash((period - LOOKAHEAD_PERIODS) * PERIOD_LENGTH),
                as_bytes32(shardId)
            )
        )
    )
    return self.validators[
        as_num128(
            num256_mod(
                h,
                as_num256(self.num_validators)
            )
        )
    ].validation_code_addr
```

### Stateless Clients

A validator is only given a few minutes' notice (precisely, `LOOKAHEAD_PERIODS * PERIOD_LENGTH` blocks worth of notice) when they are required to create a block on a given shard. In Ethereum 1.0, creating a block requires having access to the entire state in order to validate transactions. Here, our goal is to avoid requiring validators to store the state of the entire system (as that would be an O(c^2) computational resource requirement), instead allowing validators to create collations knowing only the state root, pushing the responsibility onto transaction senders to provide "witness data" (ie. Merkle branches) to prove the pre-state of the accounts the transaction affects and provide enough information to calculate the post-state root after executing the transaction.

We modify the format of a transaction so that the transaction must specify what parts of the state it can access (we describe this more precisely later; for now consider this informally as a list of addresses). Any attempt to read or write to an account outside of a transaction's specified access list during VM execution returns an error. This prevents attacks where someone sends a transaction that spends 5 million cycles of gas on random execution, then attempts to access a random account for which the transaction sender and the collator do not have a witness, preventing the collator from including the transaction and wasting their time.

_Outside_ of the signed body of the transaction, but packaged along with the transaction, the transaction sender must specify a "witness", an RLP-encoded list of Merkle tree nodes that provides the portions of the state that the transaction specifies in its access list; this allows the collator to process the transaction with only the state root. When publishing the collation, the collator also sends a witness for the entire collation.

Transaction format:

```
    [
        [nonce, acct, data....],    # transaction body
        [node1, node2, node3....]   # witness
    ]
```

Collation format:

```
    [
        [shard_id, ... , sig],   # header
        [tx1, tx2 ...],          # transaction list
        [node1, node2, node3...] # witness
        
    ]
```

See also: https://ethresear.ch/t/the-stateless-client-concept/172

### Stateless client state transition function

In general, we can describe a traditional "stateful" client as executing a state transition function `stf(state, tx) -> state'` (or `stf(state, block) -> state'`). In a stateless client model, nodes do not store the state. The functions `apply_transaction` and `apply_block` should be rewritten as follows:

```
apply_block(state_obj, witness, block) -> state_obj', reads, writes
```

Where `state_obj` is a tuple containing the state root and other O(1)-sized state data (gas used, receipts, bloom filter, etc), `witness` is a witness and `block` is the rest of the block. The returned output is:

* A new `state_obj` containing the new state root and other variables
* The set of objects from the witness that have been read (this is useful for block creation)
* The set of new state objects that have been created to form the new state trie.

This allows the functions to be "pure", as well as only dealing with small-sized objects (as opposed to the state in existing ethereum, which may reach gigabytes), making them convenient to use for sharding.

### Client Logic

A client would have a config of the following form:

```python
{
    validator_address: "0x..." OR null,
    watching: [list of shard ids],
    ...
}
```

If a validator address is provided, then it checks (on the main chain) if the address is an active validator. If it does, then every time a new period on the main chain starts (ie. when `floor(block.number / PERIOD_LENGTH)` changes), then it should call `getEligibleProposer` for all shards for period `floor(block.number / PERIOD_LENGTH) + LOOKAHEAD_PERIODS`. If it returns the validator's address for some shard `i`, then it runs the algorithm `CREATE_COLLATION(i)` (see below).

For every shard `i` in the `watching` list, every time a new collation header appears in the main chain, it downloads the full collation from the shard network, and verifies it. It locally keeps track of all valid headers (where validity is defined recursively, ie. for a header to be valid its parent must also be valid), and accepts as the main shard chain the shard chain whose head has the highest score where all collations from the genesis collation to the head are valid and available. Note that this implies the reorgs of the main chain AND reorgs of the shard chain may both influence the shard head.

### Possible algorithm for watching a shard

* Upon receiving a collation on shard `i`, verify that you have already received and validated (i) its parent, and (ii) the main chain block that it references, and attempt to process it
* To get the head at any time, scan backwards through `CollationAdded` logs shard `i` in the main chain (and specifically, those where `isNewHead = true`), and for each such log, check if you have validated the corresponding collation. If you have, then return that as the head

### CREATE_COLLATION

This process has three parts. The first part can be called `GUESS_HEAD(shard_id)`, with pseudocode here:

```python
scanning_at = main_chain.head_block_number
log_cache = []

# Fetches CollationAdded logs from the main chain, with the requirement that the shard_id
# is correct and isNewHead = true, in reverse order (ie. latest to earliest)
def get_new_head_log(shard_id):
    # Keep log_cache populated
    while len(logs_so_far) == 0:
        log_cache.extend(main_chain.get_logs(block_number=scanning_at,
                                             type=CollationAdded,
                                             req={shard_id: shard_id, isNewHead: true})[::-1])
        scanning_at -= 1
    # Whenever we want a log, we pop the first one from the list
    return log_cache.pop(0)
    
# Download a single collation and check if it is valid or invalid (memoized)
validity_cache = {}
def memoized_fetch_and_verify_collation(b):
    if b.hash not in validity_cache:
        validity_cache[b.hash] = fetch_and_verify_collation(b)
    return validity_cache[b.hash]
    
    
def main(shard_id): 
    head = None
    while 1:
        head = get_new_head_log(shard_id)
        b = head
        while 1:
            if not memoized_fetch_and_verify_collation(b):
                break
            b = get_parent(b)
```

`fetch_and_verify_collation(c)` involves fetching the full data of `c` (including witnesses) from the shard network, and verifying it. The above algorithm is equivalent to "pick the longest valid chain, check validity as far as possible, and if you find it's invalid then switch to the next-highest-scoring valid chain you know about". The algorithm should only stop when the validator runs out of time and it is time to create the collation. Every execution of `fetch_and_verify_collation` should also return a "write set" (see stateless client section above). Save all of these write sets, and combine them together; this is the `recent_trie_nodes_db`.

We then define `UPDATE_WITNESS(tx, recent_trie_nodes_db)`. While running `GUESS_HEAD`, a node will have received some transactions. When it comes time to (attempt to) include a transaction into a collation, this algorithm will need to be run on the transaction first. Suppose that the transaction has an access list `[A1 ... An]`, and a witness `W`. For each `Ai`, use the current state tree root and get the Merkle branch for `Ai`, using the union of `recent_trie_nodes_db` and `W` as a database. If the original `W` was correct, and the transaction was sent not before the time that the client checked back to, then getting this Merkle branch will always succeed. After including the transaction into a collation, the "write set" from the state change should then also be added into the `recent_trie_nodes_db`.

For illustration, here is full pseudocode for a possible transaction-gathering part of `CREATE_COLLATION`:

```python
# Sort by descending order of gasprice
txpool = sorted(copy(available_transactions), key=-tx.gasprice)
collation = new Collation(...)
while len(txpool) > 0:
    # Remove txs that ask for too much gas
    i = 0
    while i < len(txpool):
        if txpool[i].startgas > GASLIMIT - collation.gasused:
            txpool.pop(i)
        else:
            i += 1
    tx = copy.deepcopy(txpool[0])
    tx.witness = UPDATE_WITNESS(tx.witness, recent_trie_nodes_db)
    # Try to add the transaction, discard if it fails
    success, reads, writes = add_transaction(collation, tx)
    recent_trie_nodes_db = union(recent_trie_nodes_db, writes)
    txpool.pop(0)
```

At the end, there is an additional step, finalizing the collation (to give the collator the reward, which is `COLLATOR_REWARD` ETH). This requires asking the network for a Merkle branch for the collator's account. When the network replies with this, the post-state root after applying the reward, as well as the fees, can be calculated. The collator can then package up the collation, of the form (header, txs, witness), where the witness is the union of the witnesses of all the transactions and the branch for the collator's account.

## Protocol changes

### Transaction format

The format of a transaction now becomes (note that this includes [account abstraction](https://ethresear.ch/t/tradeoffs-in-account-abstraction-proposals/263/20) and [read/write lists](https://ethresear.ch/t/account-read-write-lists/285/3)):

```
    [
        chain_id,      # 1 on mainnet
        shard_id,      # the shard the transaction goes onto
        target,        # account the tx goes to
        data,          # transaction data
        start_gas,     # starting gas
        gasprice,      # gasprice
        access_list,   # access list (see below for specification)
        code           # initcode of the target (for account creation)
    ]
```

The process for applying a transaction is now as follows:

* Verify that the `chain_id` and `shard_id` are correct
* Subtract `start_gas * gasprice` wei from the `target` account
* Check if the target `account` has code. If not, verify that `sha3(code)[12:] == target`
* If the target account is empty, execute a contract creation at the `target` with `code` as init code; otherwise skip this step
* Execute a message with the remaining gas as startgas, the `target` as the to address, 0xff...ff as the sender, 0 value, and the transaction `data` as data
* If either of the two executions fail, and <= 200000 gas has been consumed (ie. `start_gas - remaining_gas <= 200000`), the transaction is invalid
* Otherwise `remaining_gas * gasprice` is refunded, and the fee paid is added to a fee counter (note: fees are NOT immediately added to the coinbase balance; instead, fees are added all at once during block finalization)

### Two-layer trie redesign

The existing account model is replaced with one where there is a single-layer trie, and all account balances, code and storage are incorporated into the trie. Specifically, the mapping is:

* Balance of account X: `sha3(X) ++ 0x00`
* Code of account X: `sha3(X) ++ 0x01`
* Storage key K of account X: `sha3(X) ++ 0x02 ++ K`

See: https://ethresear.ch/t/a-two-layer-account-trie-inside-a-single-layer-trie/210

Additionally, the trie is now a new binary trie design: https://github.com/ethereum/research/tree/master/trie_research

### Gas costs

### Rationale

This allows for a quick and dirty form of medium-security proof of stake sharding in a way that achieves quadratic scaling through separation of concerns between block proposers and collators, and thereby increases throughput by ~100x without too many changes to the protocol or software architecture. This is intended to serve as the first phase in a multi-phase plan to fully roll out quadratic sharding, the latter phases of which are described below.

### Subsequent phases

* **Phase 2, option a**: require collation headers to be added in as uncles instead of as transactions
* **Phase 2, option b**: require collation headers to be added in an array, where item `i` in the array must be either a collation header of shard `i` or the empty string, and where the extra data must be the hash of this array (soft fork)
* **Phase 3 (two-way pegging)**: add to the `USED_RECEIPT_STORE_ADDRESS` contract a function that allows receipts to be created in shards. Add to the main chain's `VALIDATOR_MANAGER_ADDRESS` a function for submitting Merkle proofs of unspent receipts that have confirmed (ie. they point to some hash `h` such that some hash `h2` exists such that `getAncestor(h2) = h` and `getAncestorDistance(h2) < 10000 * PERIOD_LENGTH * 1.33`), which has similar behavior to the `USED_RECEIPT_STORE_ADDRESS` contract in the shards.
* **Phase 4 (tight coupling)**: blocks are no longer valid if they point to invalid or unavailable collations. Add data availability proofs.
