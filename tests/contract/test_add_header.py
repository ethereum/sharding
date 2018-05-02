from sharding.handler.utils.web3_utils import (
    mine,
)
from tests.handler.fixtures import (  # noqa: F401
    smc_handler,
)
from tests.contract.utils.common_utils import (
    batch_register,
    fast_forward,
)
from tests.contract.utils.notary_account import (
    NotaryAccount,
)


def test_normal_add_header(smc_handler):  # noqa: F811
    web3 = smc_handler.web3

    # Register notary 0~2 and fast forward to next period
    batch_register(smc_handler, 0, 2)
    fast_forward(smc_handler, 1)
    current_period = web3.eth.blockNumber // smc_handler.config['PERIOD_LENGTH']
    assert current_period == 1
    # Check that collation records of shard 0 and shard 1 have not been updated before
    assert smc_handler.records_updated_period(0) == 0
    assert smc_handler.records_updated_period(1) == 0

    CHUNK_ROOT_1_0 = b'\x10' * 32
    smc_handler.add_header(1, 0, CHUNK_ROOT_1_0, private_key=NotaryAccount(0).private_key)
    mine(web3, 1)
    # Check that collation record of shard 0 has been updated
    assert smc_handler.records_updated_period(0) == 1
    assert smc_handler.get_collation_chunk_root(1, 0) == CHUNK_ROOT_1_0

    fast_forward(smc_handler, 1)
    current_period = web3.eth.blockNumber // smc_handler.config['PERIOD_LENGTH']
    assert current_period == 2

    CHUNK_ROOT_2_0 = b'\x20' * 32
    smc_handler.add_header(2, 0, CHUNK_ROOT_2_0, private_key=NotaryAccount(0).private_key)
    mine(web3, 1)
    # Check that collation record of shard 0 has been updated
    assert smc_handler.records_updated_period(0) == 2
    assert smc_handler.get_collation_chunk_root(2, 0) == CHUNK_ROOT_2_0
    # Check that collation record of shard 1 has never been updated
    assert smc_handler.records_updated_period(1) == 0

    CHUNK_ROOT_2_1 = b'\x21' * 32
    smc_handler.add_header(2, 1, CHUNK_ROOT_2_1, private_key=NotaryAccount(0).private_key)
    mine(web3, 1)
    # Check that collation record of shard 1 has been updated
    assert smc_handler.records_updated_period(1) == 2
    assert smc_handler.get_collation_chunk_root(2, 1) == CHUNK_ROOT_2_1


def test_add_header_wrong_period(smc_handler):  # noqa: F811
    web3 = smc_handler.web3
    default_gas = smc_handler.config['DEFAULT_GAS']

    # Register notary 0~2 and fast forward to next period
    batch_register(smc_handler, 0, 2)
    fast_forward(smc_handler, 1)
    current_period = web3.eth.blockNumber // smc_handler.config['PERIOD_LENGTH']
    assert current_period == 1

    BLANK_CHUNK_ROOT = b'\x00' * 32
    CHUNK_ROOT_1_0 = b'\x10' * 32
    # Attempt to add collation record with wrong period specified
    tx_hash = smc_handler.add_header(
        0,
        0,
        CHUNK_ROOT_1_0,
        private_key=NotaryAccount(0).private_key
    )
    mine(web3, 1)
    # Check that collation record of shard 0 has not been updated and transaction consume all gas
    assert smc_handler.records_updated_period(0) == 0
    assert smc_handler.get_collation_chunk_root(1, 0) == BLANK_CHUNK_ROOT
    assert web3.eth.getTransactionReceipt(tx_hash)['gasUsed'] == default_gas

    # Second attempt to add collation record with wrong period specified
    tx_hash = smc_handler.add_header(
        2,
        0,
        CHUNK_ROOT_1_0,
        private_key=NotaryAccount(0).private_key
    )
    mine(web3, 1)
    # Check that collation record of shard 0 has not been updated and transaction consume all gas
    assert smc_handler.records_updated_period(0) == 0
    assert smc_handler.get_collation_chunk_root(1, 0) == BLANK_CHUNK_ROOT
    assert web3.eth.getTransactionReceipt(tx_hash)['gasUsed'] == default_gas

    # Add correct collation record
    smc_handler.add_header(1, 0, CHUNK_ROOT_1_0, private_key=NotaryAccount(0).private_key)
    mine(web3, 1)
    # Check that collation record of shard 0 has been updated
    assert smc_handler.records_updated_period(0) == 1
    assert smc_handler.get_collation_chunk_root(1, 0) == CHUNK_ROOT_1_0


def test_add_header_wrong_shard(smc_handler):  # noqa: F811
    web3 = smc_handler.web3
    default_gas = smc_handler.config['DEFAULT_GAS']
    shard_count = smc_handler.config['SHARD_COUNT']

    # Register notary 0~2 and fast forward to next period
    batch_register(smc_handler, 0, 2)
    fast_forward(smc_handler, 1)
    current_period = web3.eth.blockNumber // smc_handler.config['PERIOD_LENGTH']
    assert current_period == 1

    BLANK_CHUNK_ROOT = b'\x00' * 32
    CHUNK_ROOT_1_0 = b'\x10' * 32
    # Attempt to add collation record with illegal shard_id specified
    tx_hash = smc_handler.add_header(
        1,
        shard_count + 1,
        CHUNK_ROOT_1_0,
        private_key=NotaryAccount(0).private_key
    )
    mine(web3, 1)
    # Check that collation record of shard 0 has not been updated and transaction consume all gas
    assert smc_handler.records_updated_period(0) == 0
    assert smc_handler.get_collation_chunk_root(1, 0) == BLANK_CHUNK_ROOT
    assert web3.eth.getTransactionReceipt(tx_hash)['gasUsed'] == default_gas

    # Second attempt to add collation record with illegal shard_id specified
    tx_hash = smc_handler.add_header(
        1,
        -1,
        CHUNK_ROOT_1_0,
        private_key=NotaryAccount(0).private_key
    )
    mine(web3, 1)
    # Check that collation record of shard 0 has not been updated and transaction consume all gas
    assert smc_handler.records_updated_period(0) == 0
    assert smc_handler.get_collation_chunk_root(1, 0) == BLANK_CHUNK_ROOT
    assert web3.eth.getTransactionReceipt(tx_hash)['gasUsed'] == default_gas

    # Add correct collation record
    smc_handler.add_header(1, 0, CHUNK_ROOT_1_0, private_key=NotaryAccount(0).private_key)
    mine(web3, 1)
    # Check that collation record of shard 0 has been updated
    assert smc_handler.records_updated_period(0) == 1
    assert smc_handler.get_collation_chunk_root(1, 0) == CHUNK_ROOT_1_0


def test_double_add_header(smc_handler):  # noqa: F811
    web3 = smc_handler.web3
    default_gas = smc_handler.config['DEFAULT_GAS']

    # Register notary 0~2 and fast forward to next period
    batch_register(smc_handler, 0, 2)
    fast_forward(smc_handler, 1)
    current_period = web3.eth.blockNumber // smc_handler.config['PERIOD_LENGTH']
    assert current_period == 1

    CHUNK_ROOT_1_0 = b'\x10' * 32
    smc_handler.add_header(1, 0, CHUNK_ROOT_1_0, private_key=NotaryAccount(0).private_key)
    mine(web3, 1)
    # Check that collation record of shard 0 has been updated
    assert smc_handler.records_updated_period(0) == 1
    assert smc_handler.get_collation_chunk_root(1, 0) == CHUNK_ROOT_1_0

    # Attempt to add collation record again with same collation record
    tx_hash = smc_handler.add_header(
        1,
        0,
        CHUNK_ROOT_1_0,
        private_key=NotaryAccount(0).private_key
    )
    mine(web3, 1)
    # Check that transaction consume all gas
    assert web3.eth.getTransactionReceipt(tx_hash)['gasUsed'] == default_gas

    # Attempt to add collation record again with different chunk root
    tx_hash = smc_handler.add_header(
        1,
        0,
        b'\x56' * 32,
        private_key=NotaryAccount(0).private_key
    )
    mine(web3, 1)
    # Check that collation record of shard 0 remains the same and transaction consume all gas
    assert smc_handler.records_updated_period(0) == 1
    assert smc_handler.get_collation_chunk_root(1, 0) == CHUNK_ROOT_1_0
    assert web3.eth.getTransactionReceipt(tx_hash)['gasUsed'] == default_gas
