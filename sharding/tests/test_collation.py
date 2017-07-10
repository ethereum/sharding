from sharding.collation import CollationHeader, Collation


def test_collation_init():
    fake_coinbase = '1111111111222222222233333333334444444444'
    collation_header = CollationHeader(coinbase=fake_coinbase)

    collation = Collation(collation_header, [])
    collation_header_dict = collation.header.to_dict()

    assert collation.transaction_count == 0
    assert collation_header_dict['coinbase'] == fake_coinbase
