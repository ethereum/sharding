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
    """

    fields = [
        ('shard_id', big_endian_int),
        ('expected_period_number', big_endian_int),
        ('period_start_prevhash', hash32),
        ('parent_collation_hash', hash32),
        ('tx_list_root', trie_root),
        ('coinbase', address),
        ('post_state_root', trie_root),
        ('receipts_root', trie_root),
        ('sig', binary)
    ]

    def __init__(self,
                 shard_id=0,
                 expected_period_number=0,
                 period_start_prevhash=utils.sha3rlp([]),
                 parent_collation_hash=utils.sha3rlp([]),
                 tx_list_root=trie.BLANK_ROOT,
                 coinbase=sharding_config['GENESIS_COINBASE'],
                 post_state_root=trie.BLANK_ROOT,
                 receipts_root=trie.BLANK_ROOT,
                 sig=''):
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
    def signing_hash(self):
        return utils.sha3(rlp.encode(self, CollationHeader.exclude(['sig'])))

    def to_dict(self):
        """Serialize the header to a readable dictionary."""
        d = {}

        for field in ('period_start_prevhash', 'parent_collation_hash',
                      'tx_list_root', 'coinbase',
                      'post_state_root', 'receipts_root', 'sig'):
            d[field] = encode_hex(getattr(self, field))

        for field in ('shard_id', 'expected_period_number'):
            d[field] = utils.to_string(getattr(self, field))

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
