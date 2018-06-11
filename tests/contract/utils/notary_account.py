from eth_tester.backends.pyevm.main import (
    get_default_account_keys,
)


class NotaryAccount:
    index = None

    def __init__(self, index):
        self.index = index

    @property
    def private_key(self):
        return get_default_account_keys()[self.index]

    @property
    def checksum_address(self):
        return self.private_key.public_key.to_checksum_address()

    @property
    def canonical_address(self):
        return self.private_key.public_key.to_canonical_address()
