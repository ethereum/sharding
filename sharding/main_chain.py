from builtins import (bytes, str, open, super, range,
                      zip, round, input, int, pow, object)
import itertools
import rlp
from rlp.utils import encode_hex

from ethereum.meta import apply_block
from ethereum.exceptions import InvalidTransaction, VerificationFailed
from ethereum.slogging import get_logger
from ethereum.pow.chain import Chain

from sharding.shard_chain import ShardChain


log = get_logger('eth.chain')


class MainChain(Chain):
    """Slightly modified pow.chain for sharding
    """

    def __init__(self, genesis=None, env=None,
                 new_head_cb=None, reset_genesis=False, localtime=None, **kwargs):
        super().__init__(
            genesis=genesis, env=env,
            new_head_cb=new_head_cb, reset_genesis=reset_genesis, localtime=localtime, **kwargs)
        self.shards = {}
        self.shard_id_list = set()

    def init_shard(self, shard_id):
        """Initialize a new ShardChain and add it to MainChain
        """
        if not self.has_shard(shard_id):
            self.shard_id_list.add(shard_id)
            self.shards[shard_id] = ShardChain(env=self.env, shard_id=shard_id)
            return True
        else:
            return False

    def add_shard(self, shard):
        """Add an existing ShardChain to MainChain
        """
        if not self.has_shard(shard.shard_id):
            self.shards[shard.shard_id] = shard
            self.shard_id_list.add(shard.shard_id)
            return True
        else:
            return False

    def has_shard(self, shard_id):
        """Check if the validator is tracking of this shard
        """
        return shard_id in self.shard_id_list

    # Call upon receiving a block, reorganize the collation head
    # TODO: Override add_block
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
            (block.header.number, encode_hex(block.header.hash)[:8], len(block.transactions), block.header.gas_used))
        if self.new_head_cb and block.header.number != 0:
            self.new_head_cb(block)
        if block.header.hash in self.parent_queue:
            for _blk in self.parent_queue[block.header.hash]:
                self.add_block(_blk)
            del self.parent_queue[block.header.hash]

        return True

    def get_expected_period_number(self):
        """Get default expected period number to be the period number of the next block
        """
        return (self.state.block_number + 1) // self.env.config['PERIOD_LENGTH']

    def get_period_start_prevhash(self, expected_period_number):
        """Get period_start_prevhash by expected_period_number
        """
        block_number = self.env.config['PERIOD_LENGTH'] * expected_period_number - 1
        period_start_prevhash = self.get_blockhash_by_number(block_number)
        if period_start_prevhash is None:
            log.info('No such block number %d' % block_number)

        return period_start_prevhash

    # TODO: test
    def update_head_collation_of_block(self, collation):
        """Update ShardChain.head_collation_of_block
        """
        shard_id = collation.header.shard_id
        collhash = collation.header.hash

        # Get the blockhash list of blocks that include the given collation
        if collhash in self.shards[shard_id].collation_blockhash_lists:
            blockhash_list = self.shards[shard_id].collation_blockhash_lists[collhash]
            while blockhash_list:
                blockhash = blockhash_list.pop(0)
                given_collation_score = self.shards[shard_id].get_score(collation)
                head_collation_score = self.shards[shard_id].get_score(self.shards[shard_id].get_head_collation(blockhash))
                if given_collation_score > head_collation_score:
                    self.shards[shard_id].head_collation_of_block[blockhash] = collhash
                    block = self.get_block(blockhash)
                    blockhash_list.extend(self.get_children(block))
        return True

    # TODO: implement in pyethapp
    # def handle_collation_header(self, collation_header):
    #     """After add_block and got the collation_header
    #     """
    #     if self.has_shard(collation_header.shard_id):
    #         collation = self.shards[collation_header.shard_id].get_collation(collation_header.hash)
    #         if collation is None:
    #             self.download_collaton(collation_header)
    #         else:
    #             self._reorganize_head_collation(collation)
    #     else:
    #         return

    # TODO: test
    def _reorganize_head_collation(self, block, collation):
        """Reorganize head collation
        """
        blockhash = block.header.hash
        collhash = collation.header.hash
        shard_id = collation.header.shard_id
        head_coll_in_prevhash = False

        # Update collation_blockhash_lists
        if self.has_shard(shard_id) and self.shards[shard_id].db.get(collhash) is not None:
            self.shards[shard_id].collation_blockhash_lists[collhash].append(blockhash)
        else:
            head_coll_in_prevhash = True

        # Compare scores
        given_collation_score = self.shards[shard_id].get_score(collation)
        head_collation_score = self.get_score(self.shards[shard_id].head_collation_of_block[blockhash])
        if given_collation_score > head_collation_score:
            self.shards[shard_id].head_collation_of_block[blockhash] = collhash
        else:
            head_coll_in_prevhash = True

        if head_coll_in_prevhash:
            self.shards[shard_id].head_collation_of_block[blockhash] = self.shards[shard_id].head_collation_of_block[block.header.prevhash]

        self.shards[shard_id].head_hash = self.shards[shard_id].head_collation_of_block[blockhash]

    def handle_ignored_collation(self, collation):
        """Handle the ignored collation (previously ignored collation)

        collation: the parent collation
        """
        if collation.header.hash in self.shards[collation.shard_id].parent_queue:
            for _collation in self.shards[collation.shard_id].parent_queue[collation.header.hash]:
                _period_start_prevblock = self.get_block(collation.header.period_start_prevhash)
                self.shards[collation.shard_id].add_collation(_collation, _period_start_prevblock, self.handle_ignored_collation)
                del self.shards[collation.shard_id].parent_queue[collation.header.hash]
        self.update_head_collation_of_block(collation)
