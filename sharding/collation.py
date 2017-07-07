# -*- coding: utf-8 -*-
import rlp
from rlp.sedes import binary, CountableList
from ethereum.utils import hash32, trie_root, \
    big_endian_int, int_to_big_endian, address, \
    encode_hex, decode_hex
from ethereum import utils
from ethereum import trie
from ethereum.transactions import Transaction
from ethereum.slogging import get_logger
from sharding.config import sharding_config


log = get_logger('eth.chain.shard')


class CollationHeader(rlp.Serializable):

    """A collation header

    [
        shard_id: uint256,
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
        ],
        mixhash: bytes32,
        nonce: uint64,
        source_block_numeber: uint256,
        source_block_hash: bytes32
    ]
    """

    fields = [
        ('shard_id', big_endian_int),
        ('prev_state_root', trie_root),
        ('tx_list_root', trie_root),
        ('coinbase', address),
        ('post_state_root', trie_root),
        ('receipt_root', trie_root),
        ('children', CountableList(hash32)),
        ('state_branch_node', hash32),
        ('signatures', CountableList(binary)),
        ('mixhash', binary),
        ('nonce', binary),
        ('source_block_numeber', big_endian_int),
        ('source_block_hash', hash32)
    ]

    def __init__(self,
                 shard_id=int_to_big_endian(0),
                 prev_state_root=trie.BLANK_ROOT,
                 tx_list_root=trie.BLANK_ROOT,
                 coinbase=sharding_config['GENESIS_COINBASE'],
                 post_state_root=trie.BLANK_ROOT,
                 receipt_root=trie.BLANK_ROOT,
                 children=[],
                 state_branch_node=utils.sha3rlp([]),
                 signatures=[],
                 mixhash='',
                 nonce='',
                 source_block_numeber=int_to_big_endian(0),
                 source_block_hash=utils.sha3rlp([])):
        fields = {k: v for k, v in locals().items() if k != 'self'}
        if len(fields['coinbase']) == 40:
            fields['coinbase'] = decode_hex(fields['coinbase'])
        assert len(fields['coinbase']) == 20
        super(CollationHeader, self).__init__(**fields)

    def __getattribute__(self, name):
        try:
            return rlp.Serializable.__getattribute__(self, name)
        except AttributeError:
            return getattr(self.header, name)

    def to_dict(self):
        """Serialize the header to a readable dictionary."""
        d = {}

        for field in ('mixhash', 'nonce',
                      'state_branch_node', 'source_block_hash'):
            d[field] = encode_hex(getattr(self, field))
        for field in ('prev_state_root', 'tx_list_root', 'post_state_root',
                      'receipt_root', 'coinbase'):
            d[field] = encode_hex(getattr(self, field))

        # [TODO] decode_int256 is unsigned or signed?
        for field in ('shard_id',
                      'source_block_numeber'):
            d[field] = utils.decode_int256(getattr(self, field))
            encode_hex(getattr(self, field))

        d['children'] = [b'0x' + encode_hex(child) for child in getattr(self, 'children')]
        d['signatures'] = [b'0x' + encode_hex(sig) for sig in getattr(self, 'signatures')]

        assert len(d) == len(CollationHeader.fields)
        return d


class Collation(rlp.Serializable):
    """A collation.

    :param header: the collation header
    :param transactions: a list of transactions which are replayed if the
                         state given by the header is not known. If the
                         state is known, `None` can be used instead of the
                         empty list.
    """

    fields = [
        ('header', CollationHeader),
        ('transactions', CountableList(Transaction))
    ]

    def __init__(self, header, transactions=None):
        self.header = header
        self.transactions = transactions or []

    def __getattribute__(self, name):
        try:
            return rlp.Serializable.__getattribute__(self, name)
        except AttributeError:
            return getattr(self.header, name)

    @property
    def transaction_count(self):
        return len(self.transactions)
