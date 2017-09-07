from builtins import super
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
            self.shards[shard_id] = ShardChain(env=self.env, shard_id=shard_id, main_chain=self)
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
                head_collation_score = self.shards[shard_id].get_score(self.shards[shard_id].head)
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
    #             self.reorganize_head_collation(collation)
    #     else:
    #         return

    def reorganize_head_collation(self, block, collation=None):
        """Reorganize head collation
        """
        # Use alias for clear code
        blockhash = block.header.hash
        if collation is None:
            collhash = shard_id = shard = None
        else:
            collhash = collation.header.hash
            shard_id = collation.header.shard_id
            shard = self.shards[shard_id]

        # Update collation_blockhash_lists
        if self.has_shard(shard_id) and shard.db.get(collhash) is not None:
            shard.collation_blockhash_lists[collhash].append(blockhash)
            # Compare score
            given_coll_score = shard.get_score(collation)
            prev_head_coll_score = shard.get_head_coll_score(block.header.prevhash)
            if given_coll_score > prev_head_coll_score:
                shard.head_collation_of_block[blockhash] = collhash
            else:
                shard.head_collation_of_block[blockhash] = shard.head_collation_of_block[block.header.prevhash]
            # Set head
            shard.head_hash = shard.head_collation_of_block[self.head_hash]
            shard.state = shard.mk_poststate_of_collation_hash(shard.head_hash)
        else:
            # The given block doesn't contain a collation
            self._reorganize_all_shards(block)

    def _reorganize_all_shards(self, block):
        """Reorganize all shards' head
        """
        blockhash = block.header.hash
        block_prevhash = block.header.prevhash
        for k in self.shards:
            if block_prevhash in self.shards[k].head_collation_of_block:
                self.shards[k].head_collation_of_block[blockhash] = self.shards[k].head_collation_of_block[block_prevhash]
                self.shards[k].head_hash = self.shards[k].head_collation_of_block[self.head_hash]
            else:
                # The shard was just initialized
                self.shards[k].head_collation_of_block[blockhash] = self.shards[k].head_hash
            self.shards[k].state = self.shards[k].mk_poststate_of_collation_hash(self.shards[k].head_hash)

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
