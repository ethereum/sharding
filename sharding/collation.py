# -*- coding: utf-8 -*-
import rlp
from rlp.sedes import binary, CountableList
from ethereum.utils import hash32, trie_root, \
    big_endian_int, address, \
    encode_hex, decode_hex
from ethereum import utils
from ethereum import trie
from ethereum.transactions import Transaction
from sharding.config import sharding_config


class CollationHeader(rlp.Serializable):

    """A collation header
    [
    shardId: uint256,
    parent_block_number: uint256,
    parent_block_hash: bytes32,
    rng_source_block_number: uint256,
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
    ]
    """

    fields = [
        ('shardId', big_endian_int),
        ('parent_block_number', big_endian_int),
        ('parent_block_hash', hash32),
        ('rng_source_block_number', big_endian_int),
        ('prev_state_root', trie_root),
        ('tx_list_root', trie_root),
        ('coinbase', address),
        ('post_state_root', trie_root),
        ('receipt_root', trie_root),
        ('children', CountableList(hash32)),
        ('state_branch_node', hash32),
        ('signatures', CountableList(binary))
    ]

    def __init__(self,
                 shardId=0,
                 parent_block_number=0,
                 parent_block_hash=utils.sha3rlp([]),
                 rng_source_block_number=0,
                 prev_state_root=trie.BLANK_ROOT,
                 tx_list_root=trie.BLANK_ROOT,
                 coinbase=sharding_config['GENESIS_COINBASE'],
                 post_state_root=trie.BLANK_ROOT,
                 receipt_root=trie.BLANK_ROOT,
                 children=[],
                 state_branch_node=utils.sha3rlp([]),
                 signatures=[],
                 mixhash='',
                 nonce=''):
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

    @property
    def hash(self):
        """The binary collation hash"""
        return utils.sha3(rlp.encode(self))

    @property
    def hex_hash(self):
        return encode_hex(self.hash)

    @property
    def mining_hash(self):
        return utils.sha3(rlp.encode(self, CollationHeader.exclude(['mixhash', 'nonce', 'signatures'])))

    @property
    def signing_hash(self):
        return utils.sha3(rlp.encode(self, CollationHeader.exclude(['extra_data'])))

    def to_dict(self):
        """Serialize the header to a readable dictionary."""
        d = {}

        for field in ('state_branch_node', 'parent_block_hash'):
            d[field] = encode_hex(getattr(self, field))
        for field in ('prev_state_root', 'tx_list_root', 'post_state_root',
                      'receipt_root', 'coinbase'):
            d[field] = encode_hex(getattr(self, field))

        for field in ('shardId',
                      'parent_block_number', 'rng_source_block_number'):
            d[field] = utils.to_string(getattr(self, field))

        d['children'] = [encode_hex(child) for child in getattr(self, 'children')]
        d['signatures'] = [encode_hex(sig) for sig in getattr(self, 'signatures')]

        assert len(d) == len(CollationHeader.fields)
        return d

    def __repr__(self):
        return '<%s(#%d %s)>' % (self.__class__.__name__, self.number,
                                 encode_hex(self.hash)[:8])

    def __eq__(self, other):
        """Two CollationHeader are equal iff they have the same hash."""
        return isinstance(other, CollationHeader) and self.hash == other.hash

    def __hash__(self):
        return utils.big_endian_to_int(self.hash)

    def __ne__(self, other):
        return not self.__eq__(other)


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
