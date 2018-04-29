import logging

from sharding.handler.utils.web3_utils import (
    get_recent_block_hashes,
    get_canonical_chain,
)


class LogHandler:

    logger = logging.getLogger("evm.chain.sharding.LogHandler")

    def __init__(self, w3, history_size=256):
        self.history_size = history_size
        self.w3 = w3
        # ----------> higher score
        self.recent_block_hashes = get_recent_block_hashes(w3, history_size)

    def get_new_logs(self, address=None, topics=None):
        # TODO: should see if we need to do something with revoked_hashes
        #       it seems reasonable to revoke logs in the blocks with hashes in `revoked_hashes`
        revoked_hashes, new_block_hashes = get_canonical_chain(
            self.w3,
            self.recent_block_hashes,
            self.history_size,
        )
        # determine `unchanged_block_hashes` by revoked_hashes
        # Note: use if/else to avoid self.recent_block_hashes[:-1 * 0]
        #       when len(revoked_hashes) == 0
        if len(revoked_hashes) != 0:
            unchanged_block_hashes = self.recent_block_hashes[:-1 * len(revoked_hashes)]
        else:
            unchanged_block_hashes = self.recent_block_hashes
        # append new blocks to `unchanged_hashes`, and move revoked ones out of
        # `self.recent_block_hashes`
        new_recent_block_hashes = unchanged_block_hashes + new_block_hashes
        # keep len(self.recent_block_hashes) <= self.history_size
        self.recent_block_hashes = new_recent_block_hashes[-1 * self.history_size:]

        if len(new_block_hashes) == 0:
            return tuple()

        from_block_hash = new_block_hashes[0]
        to_block_hash = new_block_hashes[-1]
        from_block_number = self.w3.eth.getBlock(from_block_hash)['number']
        to_block_number = self.w3.eth.getBlock(to_block_hash)['number']

        return self.w3.eth.getLogs(
            {
                'fromBlock': from_block_number,
                'toBlock': to_block_number,
                'address': address,
                'topics': topics,
            }
        )
