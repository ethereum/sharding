from ethereum.utils import encode_hex
from sharding.collation import CollationHeader, Collation


def test_collation_init():
    """Test Collation initialization
    """
    coinbase = '\x35' * 20

    collation_header = CollationHeader(coinbase=coinbase)

    collation = Collation(collation_header)
    collation_header_dict = collation.header.to_dict()

    assert collation.transaction_count == 0
    assert collation_header_dict['coinbase'] == encode_hex(coinbase)
