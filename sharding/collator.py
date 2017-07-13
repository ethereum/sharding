import copy

from ethereum.utils import sha3, decode_hex, encode_hex
from ethereum.transaction_queue import TransactionQueue
from ethereum.slogging import get_logger
from ethereum.common import mk_receipt_sha, mk_transaction_sha

from sharding import contract_utils
from sharding import state_transition

log = get_logger('sharding.collator')


def create_collation(
        chain,
        txqueue=None,
        prev_state=None,
        coinbase='\x35' * 20,
        children_header=[]):
    """Create collation on top of the given chain
    """
    log.info('Creating a collation')

    # Verify some inputs
    # NOTE: Assume the children_header is validated before
    verify_children_count(chain, children_header)

    # Apply state transition and generate collation
    temp_state = copy.deepcopy(prev_state)
    collation = state_transition.mk_collation_from_prevstate(chain, temp_state, coinbase)
    state_transition.initialize(temp_state, collation)
    state_transition.add_transactions(temp_state, collation, txqueue)
    state_transition.set_execution_results(temp_state, collation)
    # TODO finalize, incentives
    temp_state.commit()

    # Set basic fields
    collation.header.shardId = chain.shardId
    collation.header.children = [header.hash for header in children_header]
    collation.header.state_branch_node = generate_state_branch_node(
        children_header, temp_state)
    collation.header.signatures = [''] * chain.config['SIGNATURE_COUNT']

    # Set source block
    collation.header.rng_source_block_number = chain.state.block_number
    shard_head_hash = chain.get_shard_head_state()
    if shard_head_hash is not None and len(chain.parent_blocks[shard_head_hash]) > 0:
        parent_block_hash = chain.parent_blocks[shard_head_hash][-1]
        block = chain.get_block(parent_block_hash)
        collation.header.parent_block_number = block.number
        collation.header.parent_block_hash = parent_block_hash
    else:
        # The first collation of the shard
        collation.header.parent_block_number = chain.config['SERENITY_FORK_BLKNUM']
        block = chain.get_block_by_number(chain.config['SERENITY_FORK_BLKNUM'])
        collation.header.parent_block_hash = block.header.hash

    log.info('Created collation successfully')
    return collation


def verify_collation_header(
        chain,
        collation_header,
        prev_state=None,
        children_header=[],
        main_chain_included=False):
    """Verfiy the collation header only

    Use for validate the ancestors or descendants collation header
    """
    try:
        # The `coinbase` is a valid account
        # TODO: check if the coinbase is in the same shard?
        if not is_valid_account(collation_header.coinbase):
            raise ValueError("coinbase is invalid")

        # If `shardId >= 1 + SHARD_CHILD_COUNT + … + SHARD_CHILD_COUNT ** (MAX_SHARD_DEPTH-1)`, then the *children is an empty list*
        # If `shardId < 1 + SHARD_CHILD_COUNT + … + SHARD_CHILD_COUNT ** (MAX_SHARD_DEPTH-1)`, then *each entry in the children list is either an empty string, or a hash whose preimage is available*, and whose shardId is this header’s shardId multiplied by SHARD_CHILD_COUNT plus (1 + the child’s index in the list)
        verify_children_count(chain, children_header)
        if len(children_header) > 0:
            for index, child in enumerate(collation_header.children):
                if child != '' and not is_valid_child(index, child, children_header):
                    raise ValueError('child is wrong')

        # `rng_source_block_number` is a block number equal to or greater than `parent_block_number`
        if collation_header.rng_source_block_number < collation_header.parent_block_number:
            raise ValueError('rng_source_block_number is lesser than parent_block_number')

        # The `prev_state_root` is the current state root for the given shard
        if collation_header.prev_state_root != prev_state.trie.root_hash:
            raise ValueError("prev_state_root is wrong")

        # Verify signatures
        signature_result = verify_signature(chain, collation_header)
        if signature_result is None and main_chain_included:
            return False
        elif signature_result is None and not main_chain_included:
            return True
        else:
            return signature_result
    except Exception as e:
        print(str(e))
        return False
    return True


def sign_collation_header(chain, collation_header, local_validation_code_addr):
    """Check if local node is signer. If true, sign it
    """
    # TODO: Optimize the times of calling call_sample_function
    is_signed = False
    try:
        for index, sig in enumerate(collation_header.signatures):
            if len(sig) == 0:
                validation_code_addr = contract_utils.call_sample_function(
                    chain,
                    block_number=collation_header.rng_source_block_number,
                    shardId=chain.shardId,
                    sigIndex=index)
                if validation_code_addr == local_validation_code_addr:
                    # the sig is empty
                    # TODO: set collation_header.signatures[index] = local_sign
                    collation_header.signatures[index] = b'\x11'
                    is_signed = True
                    break
        return is_signed, collation_header
    except Exception as e:
        return is_signed, collation_header


def verify_collation(
        chain,
        collation,
        prev_state=None,
        children_header=[]):
    """Validate a collation
    """
    try:
        # state transition
        temp_state = copy.deepcopy(prev_state)
        apply_state_transition(chain, temp_state, collation)
        verify_execution_results(collation, temp_state, children_header)
    except Exception as e:
        print(str(e))
        return False

    return True


# [TODO]
def apply_collation(chain, prev_state, collation, block_hash, children_header=[]):
    """Apply collation
    """
    snapshot = prev_state.snapshot()
    try:
        # state transition
        temp_state = copy.deepcopy(prev_state)
        apply_state_transition(chain, temp_state, collation)
        verify_execution_results(collation, temp_state, children_header)

        chain.set_head_shard_state(collation.header, block_hash, temp_state.trie.root_hash)

        # TODO: post_finalize state, store the collation_header in state?
        # TODO: store post_state
        chain.shard_state = temp_state
    except (ValueError, AssertionError) as e:
        temp_state.revert(snapshot)
        raise e
    return temp_state


def verify_children_count(chain, children_header):
    """Verify the count of children_header is right
    """
    is_leaf = is_leaf_shard(chain.shardId, chain.config['SHARD_CHILD_COUNT'], chain.config['MAX_SHARD_DEPTH'])
    if (
        (is_leaf and len(children_header) != 0) or
        (not is_leaf and len(children_header) != chain.config['SHARD_CHILD_COUNT'])
    ):
        raise ValueError('The children count is wrong')


def generate_state_branch_node(children_header, post_state):
    """Generate the state_branch_node value
    """
    state_branch_node = None
    if len(children_header) > 0:
        concatenated_hash = post_state.trie.root_hash
        for header in children_header:
            concatenated_hash += header.state_branch_node
        state_branch_node = sha3(concatenated_hash)
    else:
        state_branch_node = post_state.trie.root_hash
    return state_branch_node


def is_valid_account(account):
    """Check if the account is valid
    """
    # TODO validate if the account is in this shard?
    if len(account) == 40:
        account = decode_hex(account)
    return True if len(account) == 20 else False


def get_geometric_progression_sum(a1, ratio, n):
    """Get geometric progression sum for checking shardId
    """
    if n == 0:
        return a1
    elif ratio == 1:
        return a1 * n
    elif ratio > 0 and n:
        return float(a1 - (ratio ** (n + 1))) / (1 - ratio)
    else:
        return a1


def is_valid_child(index, child, children_header):
    """Check if the child is valid
    """
    # TODO
    return True


def is_leaf_shard(shardId, shard_child_count, max_shard_depth):
    is_leaf = (
        shardId >=
        get_geometric_progression_sum(1, shard_child_count, max_shard_depth - 1)
    )
    return is_leaf


# [TODO]: More testing
def verify_signature(chain, collation_header):
    """Validate signatures in collation_header

    If sample function returns local_validation_code_addr, sign this collation_header
    """
    try:
        # For all `0 <= sigIndex < SIGNATURE_COUNT`, let `validationCodeAddr` be the result of calling sample(mixhash, shardId, sigIndex).
        # A signature is “valid” if calling `validationCodeAddr` on the *main shard* with 200000 gas, 0 value, the `mixhash` concatenated with the `sigIndex`’th signature as input data gives output 1. All signatures must be valid or empty, and *at least 3/4 of them must be valid*.
        if len(collation_header.signatures) > chain.config['SIGNATURE_COUNT']:
            raise ValueError('too many signatures')

        valid_signature_count = 0
        for index, sig in enumerate(collation_header.signatures):
            if len(sig) > 0:
                validation_code_addr = contract_utils.call_sample_function(
                    chain,
                    block_number=collation_header.rng_source_block_numbe,
                    shardId=chain.shardId,
                    sigIndex=index)
                if contract_utils.call_validation_code_addr(chain, validation_code_addr):
                    # TODO: This function call should be cached?
                    valid_signature_count += 1
                else:
                    raise ValueError('signature is invalid')
            elif len(sig) == 0:
                pass

        if float(valid_signature_count) / chain.config['SIGNATURE_COUNT'] < 3.0 / 4:
            # Note in Python2, / is integer division
            return None
        else:
            return True
    except Exception as e:
        str(e)
        return False


def apply_state_transition(chain, temp_state, collation):
    """Apply state transition to temp_state
    """
    txqueue = TransactionQueue()
    for tx in collation.transactions:
        txqueue.add_transaction(tx)
    temp_collation = state_transition.mk_collation_from_prevstate(chain, temp_state, collation.header.coinbase)
    state_transition.initialize(temp_state, temp_collation)
    state_transition.add_transactions(temp_state, temp_collation, txqueue)
    # TODO finalize, incentives
    temp_state.commit()


def verify_execution_results(collation, state, children_header):
    """Verify the results by Merkle Proof
    """
    if collation.header.tx_list_root != mk_transaction_sha(collation.transactions):
        raise ValueError("Transaction root mismatch: header %s computed %s" %
                         (encode_hex(collation.header.tx_list_root), encode_hex(mk_transaction_sha(collation.transactions))))
    if collation.header.post_state_root != state.trie.root_hash:
        raise ValueError("State root mismatch: header %s computed %s" %
                         (encode_hex(collation.header.post_state_root), encode_hex(state.trie.root_hash)))
    if collation.header.receipts_root != mk_receipt_sha(state.receipts):
        raise ValueError("Receipt root mismatch: header %s computed %s, computed %d, %d receipts" %
                         (encode_hex(collation.header.receipts_root), encode_hex(mk_receipt_sha(state.receipts)),
                          state.gas_used, len(state.receipts)))

    # The `state_branch_node` is the hash of the post_state_root together with the `state_branch_node` of each child; if a given child is empty then we take the current state branch node of that shard.
    state_branch_node = generate_state_branch_node(
        children_header, state)
    if collation.header.state_branch_node != state_branch_node:
        raise ValueError(
            'state_branch_node is wrong, header: %s, computed: %s',
            encode_hex(collation.header.state_branch_node), encode_hex(state_branch_node))
