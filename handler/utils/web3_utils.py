import rlp

from eth_utils import (
    to_checksum_address,
)


def get_code(web3, address):
    return web3.eth.getCode(to_checksum_address(address))


def get_nonce(web3, address):
    return web3.eth.getTransactionCount(to_checksum_address(address))


def take_snapshot(web3):
    return web3.testing.snapshot()


def revert_to_snapshot(web3, snapshot_id):
    web3.testing.revert(snapshot_id)


def mine(web3, num_blocks):
    web3.testing.mine(num_blocks)


def send_raw_transaction(web3, raw_transaction):
    raw_transaction_bytes = rlp.encode(raw_transaction)
    raw_transaction_hex = web3.toHex(raw_transaction_bytes)
    transaction_hash = web3.eth.sendRawTransaction(raw_transaction_hex)
    return transaction_hash
