import copy
import time
import itertools
import rlp
from rlp.utils import encode_hex
from collections import defaultdict

from ethereum import utils
from ethereum.meta import apply_block
from ethereum.exceptions import InvalidTransaction, VerificationFailed
from ethereum.slogging import get_logger
from ethereum.config import Env
from ethereum.state import State
from ethereum.block import Block, BLANK_UNCLES_HASH
from ethereum.pow.consensus import initialize
from ethereum.genesis_helpers import mk_basic_state, state_from_genesis_declaration, \
    initialize_genesis_keys
from ethereum.pow.chain import Chain

from sharding.collation import CollationHeader


log = get_logger('eth.chain')


def safe_decode(x):
    if x[:2] == '0x':
        x = x[2:]
    return utils.decode_hex(x)


class ShardChain(Chain):
    # Override
    def __init__(self, genesis=None, env=None,
                 new_head_cb=None, reset_genesis=False, localtime=None,
                 shardId=0, **kwargs):
        self.env = env or Env()

        # [EDITED] for sharding
        self.shardId = shardId
        # Two dict for storing the previous state
        # key: shard_header_hash, value: block_hash
        self.parent_blocks = defaultdict(list)
        # key: (shardId, block_hash), value: state_root
        self.shard_state_map = {}
        self.temp_shard_head_hash = None

        # Initialize the state
        if 'head_hash' in self.db:  # new head tag
            self.state = self.mk_poststate_of_blockhash(self.db.get('head_hash'))
            print(
                'Initializing chain from saved head, #%d (%s)' %
                (self.state.prev_headers[0].number, encode_hex(self.state.prev_headers[0].hash)))
        elif genesis is None:
            raise Exception("Need genesis decl!")
        elif isinstance(genesis, State):
            assert env is None
            self.state = genesis
            self.env = self.state.env
            print('Initializing chain from provided state')
            reset_genesis = True
        elif "extraData" in genesis:
            self.state = state_from_genesis_declaration(
                genesis, self.env)
            reset_genesis = True
            print('Initializing chain from provided genesis declaration')
        elif "prev_headers" in genesis:
            self.state = State.from_snapshot(genesis, self.env)
            reset_genesis = True
            print(
                'Initializing chain from provided state snapshot, %d (%s)' %
                (self.state.block_number, encode_hex(self.state.prev_headers[0].hash[:8])))
        elif isinstance(genesis, dict):
            print('Initializing chain from new state based on alloc')
            self.state = mk_basic_state(genesis, {
                "number": kwargs.get('number', 0),
                "gas_limit": kwargs.get('gas_limit', 4712388),
                "gas_used": kwargs.get('gas_used', 0),
                "timestamp": kwargs.get('timestamp', 1467446877),
                "difficulty": kwargs.get('difficulty', 2**25),
                "hash": kwargs.get('prevhash', '00' * 32),
                "uncles_hash": kwargs.get('uncles_hash', '0x' + encode_hex(BLANK_UNCLES_HASH))
            }, self.env)
            reset_genesis = True

        assert self.env.db == self.state.db

        initialize(self.state)
        self.new_head_cb = new_head_cb

        self.head_hash = self.state.prev_headers[0].hash
        assert self.state.block_number == self.state.prev_headers[0].number
        if reset_genesis:
            self.genesis = Block(self.state.prev_headers[0], [], [])
            initialize_genesis_keys(self.state, self.genesis)
        else:
            self.genesis = self.get_block_by_number(0)
        self.time_queue = []
        self.parent_queue = {}
        self.localtime = time.time() if localtime is None else localtime

        # TODO self.shard_state = STATE OF SERENITY FORK
        self.shard_state = copy.deepcopy(self.state)

    # Override
    # Call upon receiving a block
    def add_block(self, block):
        now = self.localtime
        # Are we receiving the block too early?
        if block.header.timestamp > now:
            i = 0
            while i < len(self.time_queue) and block.timestamp > self.time_queue[i].timestamp:
                i += 1
            self.time_queue.insert(i, block)
            log.info('Block received too early (%d vs %d). Delaying for %d seconds' %
                     (now, block.header.timestamp, block.header.timestamp - now))
            return False
        # Is the block being added to the head?
        if block.header.prevhash == self.head_hash:
            log.info('Adding to head', head=encode_hex(block.header.prevhash))
            try:
                apply_block(self.state, block)
            except (AssertionError, KeyError, ValueError, InvalidTransaction, VerificationFailed) as e:
                log.info('Block %d (%s) with parent %s invalid, reason: %s' %
                         (block.number, encode_hex(block.header.hash), encode_hex(block.header.prevhash), e))
                return False
            self.db.put(b'block:%d' % block.header.number, block.header.hash)
            block_score = self.get_score(block)  # side effect: put 'score:' cache in db
            self.head_hash = block.header.hash
            for i, tx in enumerate(block.transactions):
                self.db.put(b'txindex:' + tx.hash, rlp.encode([block.number, i]))
            assert self.get_blockhash_by_number(block.header.number) == block.header.hash
        # Or is the block being added to a chain that is not currently the head?
        elif block.header.prevhash in self.env.db:
            log.info('Receiving block not on head, adding to secondary post state',
                     prevhash=encode_hex(block.header.prevhash))
            temp_state = self.mk_poststate_of_blockhash(block.header.prevhash)
            try:
                apply_block(temp_state, block)
            except (AssertionError, KeyError, ValueError, InvalidTransaction, VerificationFailed) as e:
                log.info('Block %s with parent %s invalid, reason: %s' %
                         (encode_hex(block.header.hash), encode_hex(block.header.prevhash), e))
                return False
            block_score = self.get_score(block)
            # If the block should be the new head, replace the head
            if block_score > self.get_score(self.head):
                b = block
                new_chain = {}
                # Find common ancestor
                while b.header.number >= int(self.db.get('GENESIS_NUMBER')):
                    new_chain[b.header.number] = b
                    key = b'block:%d' % b.header.number
                    orig_at_height = self.db.get(key) if key in self.db else None
                    if orig_at_height == b.header.hash:
                        break
                    if b.prevhash not in self.db or self.db.get(b.prevhash) == 'GENESIS':
                        break
                    b = self.get_parent(b)
                # Replace block index and tx indices
                replace_from = b.header.number
                for i in itertools.count(replace_from):
                    log.info('Rewriting height %d' % i)
                    key = b'block:%d' % i
                    orig_at_height = self.db.get(key) if key in self.db else None
                    if orig_at_height:
                        self.db.delete(key)
                        orig_block_at_height = self.get_block(orig_at_height)
                        for tx in orig_block_at_height.transactions:
                            if b'txindex:' + tx.hash in self.db:
                                self.db.delete(b'txindex:' + tx.hash)
                    if i in new_chain:
                        new_block_at_height = new_chain[i]
                        self.db.put(key, new_block_at_height.header.hash)
                        for i, tx in enumerate(new_block_at_height.transactions):
                            self.db.put(b'txindex:' + tx.hash,
                                        rlp.encode([new_block_at_height.number, i]))
                    if i not in new_chain and not orig_at_height:
                        break
                self.head_hash = block.header.hash
                self.state = temp_state
        # Block has no parent yet
        else:
            if block.header.prevhash not in self.parent_queue:
                self.parent_queue[block.header.prevhash] = []
            self.parent_queue[block.header.prevhash].append(block)
            log.info('No parent found. Delaying for now')
            return False
        self.add_child(block)
        self.db.put('head_hash', self.head_hash)
        self.db.put(block.header.hash, rlp.encode(block))
        self.db.commit()
        log.info(
            'Added block %d (%s) with %d txs and %d gas' %
            (block.header.number, encode_hex(block.header.hash)[:8],
                len(block.transactions), block.header.gas_used))
        if self.new_head_cb and block.header.number != 0:
            self.new_head_cb(block)
        if block.header.hash in self.parent_queue:
            for _blk in self.parent_queue[block.header.hash]:
                self.add_block(_blk)
            del self.parent_queue[block.header.hash]

        # [EDITED] for sharding
        # check if there's collation_header in the extra_data
        # if true, update self.parent_blocks
        collation_header = None
        try:
            collation_header = rlp.decode(block.header.extra_data, CollationHeader)
        except Exception as e:
            pass
        if collation_header is not None:
            log.info('This block contains collation_header')
            for c in collation_header.children:
                self.parent_blocks[c].append(block.header.hash)
            self.parent_blocks[collation_header.hash].append(block.header.hash)

            # TODO: Remove temp_shard_head_hash after finished Scoring Algorithm
            # if (self.shardId == collation_header.shardId):
            #     self.temp_shard_head_hash = collation_header.hash

        return True

    def block_contains_collation_header(self, block_hash):
        """Check if the block contains a collation_header
        """
        try:
            block = self.get_block(block_hash)
            collation_header = rlp.decode(block.header.extra_data, CollationHeader)
            if collation_header.hash:
                return True
            else:
                return False
        except Exception as e:
            return False

    def set_head_shard_state(self, collation_header, block_hash, state_root):
        """Set the head state of shardId
        """
        self.shard_state_map[(collation_header.shardId, block_hash)] = state_root
        self.temp_shard_head_hash = collation_header.hash

    # [TODO]
    def add_collation_header(self, collation_header):
        """Add CollationHeader, update parent_blocks
        """
        assert len(self.parent_blocks[collation_header.hash]) > 0
        for block_hash in self.parent_blocks[collation_header.hash]:
            if (self.block_contains_collation_header(block_hash)):
                # TODO: Verify collation_header in conext of block_hash
                for child in collation_header.children:
                    self.parent_blocks[child].append(block_hash)

    # [TODO]
    def get_shard_head_state(self):
        """Return the shard head state
        """
        shard_head_hash = self.get_shard_head_hash()
        if shard_head_hash in self.parent_blocks:
            block_hash = self.parent_blocks[shard_head_hash][-1]
            if (self.shardId, block_hash) in self.shard_state_map:
                state_root = self.shard_state_map[(self.shardId, block_hash)]

                # TODO: get privous state by state_root like chain.py
                return self.shard_state  # temporary, just use last shard_state
            else:
                return self.shard_state
        else:
            log.info('First collation')
            return self.shard_state
        return None

    # [TODO]
    def get_shard_head_hash(self):
        """Return the shard head hash of shardId
        """
        # TODO: Scoring to find the longest chain
        return self.temp_shard_head_hash

    # [TODO]
    def get_prev_state(self, block_hash):
        """Get previous state
        """
        # TODO Get previous state like chain.py
        return self.shard_state
