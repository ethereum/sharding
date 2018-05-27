import itertools

import pytest

from cytoolz.dicttoolz import (
    assoc,
)

from web3 import (
    Web3,
)

from web3.providers.eth_tester import (
    EthereumTesterProvider,
)

from eth_utils import (
    event_signature_to_log_topic,
)

from eth_tester import (
    EthereumTester,
    PyEVMBackend,
)
from eth_tester.backends.pyevm.main import (
    get_default_account_keys,
)

from sharding.handler.log_handler import (
    LogHandler,
)
from sharding.handler.utils.web3_utils import (
    mine,
    take_snapshot,
    revert_to_snapshot,
)


code = """
Test: __log__({amount1: num})

@public
def emit_log(log_number: num):
    log.Test(log_number)
"""
abi = [{'name': 'Test', 'inputs': [{'type': 'int128', 'name': 'amount1', 'indexed': False}], 'anonymous': False, 'type': 'event'}, {'name': 'emit_log', 'outputs': [], 'inputs': [{'type': 'int128', 'name': 'log_number'}], 'constant': False, 'payable': False, 'type': 'function'}]  # noqa: E501
bytecode = b'a\x00\xf9V`\x005`\x1cRt\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00` Ro\x7f\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff`@R\x7f\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\x80\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00``Rt\x01*\x05\xf1\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xfd\xab\xf4\x1c\x00`\x80R\x7f\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xfe\xd5\xfa\x0e\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00`\xa0Rc\xd0(}7`\x00Q\x14\x15a\x00\xf4W` `\x04a\x01@74\x15\x15XW``Q`\x045\x80`@Q\x90\x13XW\x80\x91\x90\x12XWPa\x01@Qa\x01`R\x7f\xaeh\x04lU;\x85\xd0\x8bolL6\x92S)\x06\xf3M\x1d\xa6\xcb\x032\x1e\xd6\x96\xca\x0b\xdcL\xad` a\x01`\xa1\x00[[a\x00\x04a\x00\xf9\x03a\x00\x04`\x009a\x00\x04a\x00\xf9\x03`\x00\xf3'  # noqa: E501

test_keys = get_default_account_keys()
privkey = test_keys[0]
default_tx_detail = {
    'from': privkey.public_key.to_checksum_address(),
    'gas': 500000,
}
test_event_signature = event_signature_to_log_topic("Test(int128)")

HISTORY_SIZE = 256


@pytest.fixture
def contract():
    eth_tester = EthereumTester(
        backend=PyEVMBackend(),
        auto_mine_transactions=False,
    )
    provider = EthereumTesterProvider(eth_tester)
    w3 = Web3(provider)
    tx_hash = w3.eth.sendTransaction(assoc(default_tx_detail, 'data', bytecode))
    mine(w3, 1)
    receipt = w3.eth.getTransactionReceipt(tx_hash)
    contract_address = receipt['contractAddress']
    return w3.eth.contract(contract_address, abi=abi, bytecode=bytecode)


def test_get_logs_without_forks(contract, smc_testing_config):
    period_length = smc_testing_config['PERIOD_LENGTH']
    w3 = contract.web3
    log_handler = LogHandler(w3, period_length=period_length)
    counter = itertools.count()

    contract.functions.emit_log(next(counter)).transact(default_tx_detail)
    mine(w3, 1)
    logs_block2 = log_handler.get_logs(address=contract.address)
    assert len(logs_block2) == 1
    assert int(logs_block2[0]['data'], 16) == 0
    mine(w3, period_length - 1)

    contract.functions.emit_log(next(counter)).transact(default_tx_detail)
    mine(w3, 1)
    logs_block3 = log_handler.get_logs(address=contract.address)
    assert len(logs_block3) == 1
    assert int(logs_block3[0]['data'], 16) == 1
    mine(w3, period_length - 1)

    contract.functions.emit_log(next(counter)).transact(default_tx_detail)
    mine(w3, 1)
    contract.functions.emit_log(next(counter)).transact(default_tx_detail)
    mine(w3, 1)
    logs_block4_5 = log_handler.get_logs(address=contract.address)
    assert len(logs_block4_5) == 2
    assert int(logs_block4_5[0]['data'], 16) == 2
    assert int(logs_block4_5[1]['data'], 16) == 3


def test_get_logs_with_forks(contract, smc_testing_config):
    w3 = contract.web3
    log_handler = LogHandler(w3, period_length=smc_testing_config['PERIOD_LENGTH'])
    counter = itertools.count()
    snapshot_id = take_snapshot(w3)
    current_block_number = w3.eth.blockNumber

    contract.functions.emit_log(next(counter)).transact(default_tx_detail)
    mine(w3, 1)
    revert_to_snapshot(w3, snapshot_id)
    assert w3.eth.blockNumber == current_block_number
    contract.functions.emit_log(next(counter)).transact(default_tx_detail)
    mine(w3, 1)
    contract.functions.emit_log(next(counter)).transact(default_tx_detail)
    mine(w3, 1)
    logs = log_handler.get_logs()
    # assert len(logs) == 2
    assert int(logs[0]['data'], 16) == 1
    assert int(logs[1]['data'], 16) == 2
