### Parameters

* `READ_ADDRESS_GAS`: 2000
* `READ_BYTE_GAS`: 3
* `EXPAND_BYTE_GAS`: 300
* `ACCOUNT_EDIT_COST`: 8000

### Specification

* Accounts no longer have a storage tree. Instead, the `storage_root` field of an account is replaced by a `storage_hash`, which is the hash of a storage byte array (empty by default)
* In each transaction, we add two fields: `read_address_list` and `write_address_list`. We charge extra gas: `READ_ADDRESS_GAS * len(union(read_address_list, write_address_list)) + READ_BYTE_GAS * sum([len(code(x)) + len(storage(x)) for x in union(read_address_list, write_address_list)])`
* A transaction is only allowed to access accounts that are in the `read_address_list` or are precompiles; it is only allowed to modify accounts that are in the `write_address_list`. Violations immediately throw an exception.
* While executing a transaction, the EVM keeps track of the set of accounts that have already been modified via SSTORE. The gas cost of SSTORE is now as follows:
    * Let `ACCESS_COST` = `ACCOUNT_EDIT_COST` if the account has not yet been SSTORE'd, otherwise 100
    * Let `EXPANSION_COST` = 0 if `sstore_arg <= len(storage) - 32`, else `EXPAND_BYTE_GAS * (sstore_arg - (len(storage) - 32))`
    * The total cost is `ACCESS_COST + EXPANSION_COST`
* `SLOAD` and `SSTORE` read and write to the storage byte array much like `MLOAD` and `MSTORE`, though `SLOAD` does not expand storage (only `SSTORE` does)
* The `CREATE` opcode is removed; only `CREATE2` is available. We also add `CREATE_COPY`, which is equal to `CREATE2` with one modification: it expects as output exactly 32 bytes (throwing an exception if return data size is not 32 bytes), of which the last 20 are parsed as an address, and code is copied from this address. 0 gas is charged at return time for creating the contract.
* Introduces an opcode SCOPY (similar in form to CALLDATACOPY except copying memory to storage), which costs the same as `SSTORE` minus 3 gas, but adding 3 gas per 32 bytes copied (rounding up to the nearest 32 if the size is not an even multiple). `EXPANSION_COST` is equal to 0 if `SCOPY` copies zero bytes or if the copy operation copies into storage space that already exists; otherwise it is equal to `EXPAND_BYTE_GAS * (new_storage_length - old_storage_length)`

### Rationale

This design introduces several important benefits:

1. It introduces parallelizability equivalent to that offered by [EIP 648](https://github.com/ethereum/EIPs/issues/648) with its read and write spaces.
2. It requires transactions to fully specify which accounts they can access or modify, paving the way for much easier development of various scalability designs involving Merkle proofs.
3. It makes the common pattern of creating many contracts with the same code much cheaper in terms of gas costs, making complex EIP 86 accounts, deed contracts, identity contracts and various other object-oriented constructions much more affordable (as they should be; storing the same code many times is cheap with trivially-implementable deduplication).
4. It makes contracts that have several variables that get updated at the same time cheaper to execute, as it is no longer necessary to make storage tree modifications for every single value.
5. It effectively deals with the incentive incompatibility inherent in the current design, where SLOADing is equally expensive regardless of whether there are 2 storage keys or 2000000, even though in the latter case the operation is at least 5 times more expensive and possibly substantially more.
6. It makes storage operate in the same way as memory, creating perfect symmetry between calldata, returndata, memory and storage.

A particularly interesting consequence is that it opens the door to _stateless full clients_. Stateless full clients download full blocks and process every transaction, but maintain no state beyond the state root. To accomplish this, they expect transactions to come in a wrapper, where every address in `read_address_list` and `write_address_list` comes with a Merkle proof showing that the address is in the state tree with a recent state root. A stateless client rejects transactions if the Merkle proofs point to a state root from before the time the stateless client logged on, and maintains a cache of all new trie nodes created by transaction execution; this way if a given proof is outdated the client will still be able to construct an updated proof showing membership in the current state.

There is actually an entire continuum of statefulness for clients: clients could store the full state, they could store no state except for state roots, they could only store the top three levels of the state Merkle tree, or they could store all accounts, but not their code and storage. For each "level" of statefulness that is formally standardized, there would be an associated transaction bundle format which would attach the required auxiliary information for the client to process it.

Another benefit of this is that it makes it substantially easier to implement storage rent schemes, because the design inherently makes it prohibitive to create single contracts whose storage has unbounded size; instead, it forces developers to represent unbounded lists and mappings (eg. ERC20 token balances) by creating separate contracts for each entry in such a list or mapping. Developers would then need to reason about which parties are harmed if some particular item in a mapping is unexpectedly reset to zero, and provide tooling for those parties to pay ether to top up the contracts that are economically relevant to them.

### Implementation

Because of the extreme backwards incompatibilty of the design, it's recommended to introduce this design in all shards _except_ for the original "home shard" when sharding is rolled out.
