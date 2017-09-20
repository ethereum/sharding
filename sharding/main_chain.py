from builtins import super
import itertools

import rlp
from rlp.sedes import List, binary

from ethereum.slogging import get_logger
from ethereum.pow.chain import Chain
from ethereum.utils import (
    sha3, hash32,
    big_endian_to_int, encode_hex)
from ethereum import utils
from ethereum.meta import apply_block
from ethereum.exceptions import InvalidTransaction, VerificationFailed
from ethereum.db import RefcountDB

from sharding.shard_chain import ShardChain
from sharding.validator_manager_utils import ADD_HEADER_TOPIC

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
        self.add_header_logs = []

    # Call upon receiving a block
    def add_block(self, block):
        now = self.localtime
        missing_collations = {}
        # Are we receiving the block too early?
        if block.header.timestamp > now:
            i = 0
            while i < len(
                    self.time_queue) and block.timestamp > self.time_queue[i].timestamp:
                i += 1
            self.time_queue.insert(i, block)
            log.info('Block received too early (%d vs %d). Delaying for %d seconds' %
                     (now, block.header.timestamp, block.header.timestamp - now))
            return False, {}
        # Is the block being added to the head?
        if block.header.prevhash == self.head_hash:
            log.info('Adding to head',
                     head=encode_hex(block.header.prevhash[:4]))
            self.state.deletes = []
            self.state.changed = {}
            try:
                apply_block(self.state, block)
            except (AssertionError, KeyError, ValueError, InvalidTransaction, VerificationFailed) as e:
                log.info('Block %d (%s) with parent %s invalid, reason: %s' %
                         (block.number, encode_hex(block.header.hash[:4]), encode_hex(block.header.prevhash[:4]), str(e)))
                return False
            self.db.put(b'block:%d' % block.header.number, block.header.hash)
            # side effect: put 'score:' cache in db
            block_score = self.get_score(block)
            self.head_hash = block.header.hash
            for i, tx in enumerate(block.transactions):
                self.db.put(b'txindex:' +
                            tx.hash, rlp.encode([block.number, i]))
            assert self.get_blockhash_by_number(
                block.header.number) == block.header.hash
            deletes = self.state.deletes
            changed = self.state.changed
        # Or is the block being added to a chain that is not currently the
        # head?
        elif block.header.prevhash in self.env.db:
            log.info('Receiving block %d (%s) not on head (%s), adding to secondary post state %s' %
                     (block.number, encode_hex(block.header.hash[:4]),
                      encode_hex(self.head_hash[:4]), encode_hex(block.header.prevhash[:4])))
            temp_state = self.mk_poststate_of_blockhash(block.header.prevhash)
            try:
                apply_block(temp_state, block)
            except (AssertionError, KeyError, ValueError, InvalidTransaction, VerificationFailed) as e:
                log.info(
                    'Block %s with parent %s invalid, reason: %s' %
                    (encode_hex(block.header.hash[:4]), encode_hex(block.header.prevhash[:4]), str(e)))
                return False, {}
            deletes = temp_state.deletes
            block_score = self.get_score(block)
            changed = temp_state.changed
            # If the block should be the new head, replace the head
            if block_score > self.get_score(self.head):
                b = block
                new_chain = {}
                # Find common ancestor
                while b.header.number >= int(self.db.get('GENESIS_NUMBER')):
                    new_chain[b.header.number] = b
                    key = b'block:%d' % b.header.number
                    orig_at_height = self.db.get(
                        key) if key in self.db else None
                    if orig_at_height == b.header.hash:
                        break
                    if b.prevhash not in self.db or self.db.get(
                            b.prevhash) == 'GENESIS':
                        break
                    b = self.get_parent(b)
                replace_from = b.header.number
                # Replace block index and tx indices, and edit the state cache

                # Get a list of all accounts that have been edited along the old and
                # new chains
                changed_accts = {}
                # Read: for i in range(common ancestor block number...new block
                # number)
                for i in itertools.count(replace_from):
                    log.info('Rewriting height %d' % i)
                    key = b'block:%d' % i
                    # Delete data for old blocks
                    orig_at_height = self.db.get(
                        key) if key in self.db else None
                    if orig_at_height:
                        orig_block_at_height = self.get_block(orig_at_height)
                        log.info(
                            '%s no longer in main chain' %
                            encode_hex(
                                orig_block_at_height.header.hash))
                        # Delete from block index
                        self.db.delete(key)
                        # Delete from txindex
                        for tx in orig_block_at_height.transactions:
                            if b'txindex:' + tx.hash in self.db:
                                self.db.delete(b'txindex:' + tx.hash)
                        # Add to changed list
                        acct_list = self.db.get(
                            b'changed:' + orig_block_at_height.hash)
                        for j in range(0, len(acct_list), 20):
                            changed_accts[acct_list[j: j + 20]] = True
                    # Add data for new blocks
                    if i in new_chain:
                        new_block_at_height = new_chain[i]
                        log.info(
                            '%s now in main chain' %
                            encode_hex(
                                new_block_at_height.header.hash))
                        # Add to block index
                        self.db.put(key, new_block_at_height.header.hash)
                        # Add to txindex
                        for j, tx in enumerate(
                                new_block_at_height.transactions):
                            self.db.put(b'txindex:' + tx.hash,
                                        rlp.encode([new_block_at_height.number, j]))
                        # Add to changed list
                        if i < b.number:
                            acct_list = self.db.get(
                                b'changed:' + new_block_at_height.hash)
                            for j in range(0, len(acct_list), 20):
                                changed_accts[acct_list[j: j + 20]] = True
                    if i not in new_chain and not orig_at_height:
                        break
                # Add changed list from new head to changed list
                for c in changed.keys():
                    changed_accts[c] = True
                # Update the on-disk state cache
                for addr in changed_accts.keys():
                    data = temp_state.trie.get(addr)
                    if data:
                        self.state.db.put(b'address:' + addr, data)
                    else:
                        try:
                            self.state.db.delete(b'address:' + addr)
                        except KeyError:
                            pass
                self.head_hash = block.header.hash
                self.state = temp_state
                self.state.executing_on_head = True
        # Block has no parent yet
        else:
            if block.header.prevhash not in self.parent_queue:
                self.parent_queue[block.header.prevhash] = []
            self.parent_queue[block.header.prevhash].append(block)
            log.info('Got block %d (%s) with prevhash %s, parent not found. Delaying for now' %
                     (block.number, encode_hex(block.hash[:4]), encode_hex(block.prevhash[:4])))
            return False, {}
        self.add_child(block)
        self.db.put('head_hash', self.head_hash)
        self.db.put(block.hash, rlp.encode(block))
        self.db.put(b'changed:' + block.hash,
                    b''.join([k.encode() if isinstance(k,
                                                       str) else k for k in list(changed.keys())]))
        # print('Saved %d address change logs' % len(changed.keys()))
        self.db.put(b'deletes:' + block.hash, b''.join(deletes))
        log.debug('Saved %d trie node deletes for block %d (%s)' %
                  (len(deletes), block.number, utils.encode_hex(block.hash)))
        # Delete old junk data
        old_block_hash = self.get_blockhash_by_number(
            block.number - self.max_history)
        if old_block_hash:
            try:
                deletes = self.db.get(b'deletes:' + old_block_hash)
                log.debug(
                    'Deleting up to %d trie nodes' %
                    (len(deletes) // 32))
                rdb = RefcountDB(self.db)
                for i in range(0, len(deletes), 32):
                    rdb.delete(deletes[i: i + 32])
                self.db.delete(b'deletes:' + old_block_hash)
                self.db.delete(b'changed:' + old_block_hash)
            except KeyError as e:
                print(e)
                pass
        self.db.commit()
        assert (b'deletes:' + block.hash) in self.db
        log.info('Added block %d (%s) with %d txs and %d gas' %
                 (block.header.number, encode_hex(block.header.hash)[:8],
                  len(block.transactions), block.header.gas_used))
        # Call optional callback
        if self.new_head_cb and block.header.number != 0:
            self.new_head_cb(block)
        # Are there blocks that we received that were waiting for this block?
        # If so, process them.
        if block.header.hash in self.parent_queue:
            for _blk in self.parent_queue[block.header.hash]:
                if len(self.state.log_listeners) == 0:
                    self.append_log_listener()

                self.add_block(_blk)

                # FIXME check_collation
                collation_map, missing_collations_map = self.parse_add_header_logs(block)
                for i in missing_collations_map:
                    if i not in missing_collations:
                        missing_collations[i] = {}
                    missing_collations[i].update(missing_collations_map[i])
                print('[in parent_queue] Reorganizing......')
                for shard_id in self.shard_id_list:
                    # FIXME not this self.shard_id_list
                    collation = collation_map[shard_id] if shard_id in collation_map else None
                    self.reorganize_head_collation(_blk, collation)

            del self.parent_queue[block.header.hash]
        return True, missing_collations

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
            shard.main_chain = self
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
        return (self.head.number + 1) // self.env.config['PERIOD_LENGTH']

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
        # alias
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
                    blockhash_list.extend([b.header.hash for b in self.get_children(block)])
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
        if self.has_shard(shard_id) and collhash and shard.db.get(collhash):
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
                try:
                    self.shards[k].head_hash = self.shards[k].head_collation_of_block[self.head_hash]
                except KeyError:
                    print('head_hash {} not in head_collation_of_block'.format(encode_hex(self.head_hash)))
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
                self.shards[collation.shard_id].add_collation(_collation, _period_start_prevblock, self.handle_ignored_collation, self.update_head_collation_of_block)
                del self.shards[collation.shard_id].parent_queue[collation.header.hash]

    def append_log_listener(self):
        """ Append log_listeners
        """
        def header_log_listener(log):
            print('log:{}'.format(log))
            for x in log.topics:
                if x == big_endian_to_int(ADD_HEADER_TOPIC):
                    self.add_header_logs.append(log.data)
        self.state.log_listeners.append(header_log_listener)

    def parse_add_header_logs(self, block):
        """ Parse add_header_logs, check if there are the collation headers that the validator is watching
        """
        collation_map = {}
        missing_collations_map = {}
        for item in self.add_header_logs:
            log.info('Got log item form self.add_header_logs!')
            # [num, num, bytes32, bytes32, bytes32, address, bytes32, bytes32, bytes]
            # use sedes to prevent integer 0 from being decoded as b''
            sedes = List([utils.big_endian_int, utils.big_endian_int, hash32, hash32, hash32, utils.address, hash32, hash32, utils.big_endian_int, binary])
            values = rlp.decode(item, sedes)
            shard_id = values[0]
            log.info("add_header: shard_id={}, expected_period_number={}, header_hash={}, parent_header_hash={}".format(values[0], values[1], encode_hex(utils.sha3(item)), encode_hex(values[3])))
            if shard_id in self.shard_id_list and self.shards[shard_id].active:
                collation_hash = sha3(item)
                collation = self.shards[shard_id].get_collation(collation_hash)
                if collation is None:
                    # Getting add_header before getting collation
                    # Request for collation and put the task into waiting queue
                    if shard_id not in missing_collations_map:
                        missing_collations_map[shard_id] = {}
                    missing_collations_map[shard_id][collation_hash] = block
                    # self.request_collation(shard_id, collation_hash)
                    # self.shard_data[shard_id].missing_collations[collation_hash] = block
                else:
                    collation_map[shard_id] = collation

        # Clear add_header_logs cache
        self.add_header_logs = []

        return collation_map, missing_collations_map
