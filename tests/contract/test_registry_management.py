from handler.utils.web3_utils import (
    mine,
)
from tests.handler.fixtures import (  # noqa: F401
    smc_handler,
)
from tests.contract.utils.notary_account import (
    TestingNotaryAccount,
)


def test_normal_register(smc_handler):  # noqa: F811
    web3 = smc_handler.web3

    notary_0 = TestingNotaryAccount(0)

    does_notary_exist = smc_handler.does_notary_exist(notary_0.checksum_address)
    assert not does_notary_exist
    # Register notary 0
    smc_handler.register_notary(private_key=notary_0.private_key)
    mine(web3, 1)
    does_notary_exist = smc_handler.does_notary_exist(notary_0.checksum_address)
    assert does_notary_exist
    notary_deregistered_period, notary_pool_index = smc_handler.get_notary_info(
        notary_0.checksum_address
    )
    assert notary_deregistered_period == 0 and notary_pool_index == 0
    notary_pool_length = smc_handler.notary_pool_len()
    assert notary_pool_length == 1

    notary_1 = TestingNotaryAccount(1)

    notary_2 = TestingNotaryAccount(2)

    # Register notary 1 and notary 2
    smc_handler.register_notary(private_key=notary_1.private_key)
    smc_handler.register_notary(private_key=notary_2.private_key)
    mine(web3, 1)

    does_notary_exist = smc_handler.does_notary_exist(notary_1.checksum_address)
    assert does_notary_exist
    notary_deregistered_period, notary_pool_index = smc_handler.get_notary_info(
        notary_1.checksum_address
    )
    assert notary_deregistered_period == 0 and notary_pool_index == 1

    does_notary_exist = smc_handler.does_notary_exist(notary_2.checksum_address)
    assert does_notary_exist
    notary_deregistered_period, notary_pool_index = smc_handler.get_notary_info(
        notary_2.checksum_address
    )
    assert notary_deregistered_period == 0 and notary_pool_index == 2

    notary_pool_length = smc_handler.notary_pool_len()
    assert notary_pool_length == 3


def test_register_without_enough_ether(smc_handler):  # noqa: F811
    web3 = smc_handler.web3
    default_gas = smc_handler.config['DEFAULT_GAS']

    notary_0 = TestingNotaryAccount(0)

    does_notary_exist = smc_handler.does_notary_exist(notary_0.checksum_address)
    assert not does_notary_exist

    # Register without enough ether
    smc_handler._send_transaction(
        'register_notary',
        [],
        private_key=notary_0.private_key,
        value=smc_handler.config['NOTARY_DEPOSIT'] // 10000,
        gas=default_gas,
    )
    mine(web3, 1)

    # Check that the registration failed
    does_notary_exist = smc_handler.does_notary_exist(notary_0.checksum_address)
    assert not does_notary_exist
    notary_pool_length = smc_handler.notary_pool_len()
    assert notary_pool_length == 0


def test_double_register(smc_handler):  # noqa: F811
    web3 = smc_handler.web3
    default_gas = smc_handler.config['DEFAULT_GAS']

    notary_0 = TestingNotaryAccount(0)

    # Register notary 0
    smc_handler.register_notary(private_key=notary_0.private_key)
    mine(web3, 1)
    does_notary_exist = smc_handler.does_notary_exist(notary_0.checksum_address)
    assert does_notary_exist
    notary_pool_length = smc_handler.notary_pool_len()
    assert notary_pool_length == 1

    # Try register notary 0 again
    tx_hash = smc_handler.register_notary(private_key=notary_0.private_key)
    mine(web3, 1)
    # Check pool remain the same and the transaction consume all gas
    notary_pool_length = smc_handler.notary_pool_len()
    assert notary_pool_length == 1
    assert web3.eth.getTransactionReceipt(tx_hash)['gasUsed'] == default_gas


def test_normal_deregister(smc_handler):  # noqa: F811
    web3 = smc_handler.web3

    notary_0 = TestingNotaryAccount(0)

    # Register notary 0
    smc_handler.register_notary(private_key=notary_0.private_key)
    mine(web3, 1)
    does_notary_exist = smc_handler.does_notary_exist(notary_0.checksum_address)
    assert does_notary_exist
    notary_pool_length = smc_handler.notary_pool_len()
    assert notary_pool_length == 1

    # Fast foward
    mine(web3, 100 - web3.eth.blockNumber)

    # Deregister notary 0
    smc_handler.deregister_notary(private_key=notary_0.private_key)
    current_period = web3.eth.blockNumber // smc_handler.config['PERIOD_LENGTH']
    mine(web3, 1)
    does_notary_exist = smc_handler.does_notary_exist(notary_0.checksum_address)
    assert does_notary_exist
    notary_deregistered_period, notary_pool_index = smc_handler.get_notary_info(
        notary_0.checksum_address
    )
    assert notary_deregistered_period == current_period
    notary_pool_length = smc_handler.notary_pool_len()
    assert notary_pool_length == 0


def test_deregister_then_register(smc_handler):  # noqa: F811
    web3 = smc_handler.web3
    default_gas = smc_handler.config['DEFAULT_GAS']

    notary_0 = TestingNotaryAccount(0)

    # Register notary 0
    smc_handler.register_notary(private_key=notary_0.private_key)
    mine(web3, 1)
    does_notary_exist = smc_handler.does_notary_exist(notary_0.checksum_address)
    assert does_notary_exist
    notary_pool_length = smc_handler.notary_pool_len()
    assert notary_pool_length == 1

    # Fast foward
    mine(web3, 100 - web3.eth.blockNumber)

    # Deregister notary 0
    smc_handler.deregister_notary(private_key=notary_0.private_key)
    current_period = web3.eth.blockNumber // smc_handler.config['PERIOD_LENGTH']
    mine(web3, 1)
    does_notary_exist = smc_handler.does_notary_exist(notary_0.checksum_address)
    assert does_notary_exist
    notary_deregistered_period, notary_pool_index = smc_handler.get_notary_info(
        notary_0.checksum_address
    )
    assert notary_deregistered_period == current_period
    notary_pool_length = smc_handler.notary_pool_len()
    assert notary_pool_length == 0

    # Register again right away
    tx_hash = smc_handler.register_notary(private_key=notary_0.private_key)
    mine(web3, 1)
    # Check pool remain the same and the transaction consume all gas
    notary_pool_length = smc_handler.notary_pool_len()
    assert notary_pool_length == 0
    assert web3.eth.getTransactionReceipt(tx_hash)['gasUsed'] == default_gas


def test_normal_release_notary(smc_handler):  # noqa: F811
    SIM_NOTARY_LOCKUP_LENGTH = 120

    web3 = smc_handler.web3

    notary_0 = TestingNotaryAccount(0)

    # Register notary 0
    smc_handler.register_notary(private_key=notary_0.private_key)
    mine(web3, 1)
    does_notary_exist = smc_handler.does_notary_exist(notary_0.checksum_address)
    assert does_notary_exist
    notary_pool_length = smc_handler.notary_pool_len()
    assert notary_pool_length == 1

    # Fast foward
    mine(web3, 50 - web3.eth.blockNumber)

    # Deregister notary 0
    smc_handler.deregister_notary(private_key=notary_0.private_key)
    mine(web3, 1)
    notary_pool_length = smc_handler.notary_pool_len()
    assert notary_pool_length == 0

    # Fast foward
    mine(web3, SIM_NOTARY_LOCKUP_LENGTH * (smc_handler.config['PERIOD_LENGTH'] + 1))

    # Release notary 0
    smc_handler.release_notary(private_key=notary_0.private_key)
    mine(web3, 1)
    does_notary_exist = smc_handler.does_notary_exist(notary_0.checksum_address)
    assert not does_notary_exist


def test_instant_release_notary(smc_handler):  # noqa: F811
    web3 = smc_handler.web3
    default_gas = smc_handler.config['DEFAULT_GAS']

    notary_0 = TestingNotaryAccount(0)

    # Register notary 0
    smc_handler.register_notary(private_key=notary_0.private_key)
    mine(web3, 1)
    does_notary_exist = smc_handler.does_notary_exist(notary_0.checksum_address)
    assert does_notary_exist
    notary_pool_length = smc_handler.notary_pool_len()
    assert notary_pool_length == 1

    # Fast foward
    mine(web3, 50 - web3.eth.blockNumber)

    # Deregister notary 0
    smc_handler.deregister_notary(private_key=notary_0.private_key)
    mine(web3, 1)
    notary_pool_length = smc_handler.notary_pool_len()
    assert notary_pool_length == 0

    # Instant release notary 0
    tx_hash = smc_handler.release_notary(private_key=notary_0.private_key)
    mine(web3, 1)
    # Check registry remain the same and the transaction consume all gas
    does_notary_exist = smc_handler.does_notary_exist(notary_0.checksum_address)
    assert does_notary_exist
    assert web3.eth.getTransactionReceipt(tx_hash)['gasUsed'] == default_gas


def test_deregister_and_new_notary_register(smc_handler):  # noqa: F811
    web3 = smc_handler.web3

    notary_0 = TestingNotaryAccount(0)

    # Register notary 0
    smc_handler.register_notary(private_key=notary_0.private_key)
    mine(web3, 1)
    notary_pool_length = smc_handler.notary_pool_len()
    assert notary_pool_length == 1

    notary_1 = TestingNotaryAccount(1)

    notary_2 = TestingNotaryAccount(2)

    notary_3 = TestingNotaryAccount(3)

    # Register notary 1 and notary 2
    smc_handler.register_notary(private_key=notary_1.private_key)
    smc_handler.register_notary(private_key=notary_2.private_key)
    smc_handler.register_notary(private_key=notary_3.private_key)
    mine(web3, 1)

    notary_pool_length = smc_handler.notary_pool_len()
    assert notary_pool_length == 4
    # Check that empty_slots_stack is empty
    empty_slots_stack_top = smc_handler.empty_slots_stack_top()
    assert empty_slots_stack_top == 0

    # Fast foward
    mine(web3, 50 - web3.eth.blockNumber)

    # Deregister notary 2
    smc_handler.deregister_notary(private_key=notary_2.private_key)
    mine(web3, 1)
    notary_pool_length = smc_handler.notary_pool_len()
    assert notary_pool_length == 3

    # Check that empty_slots_stack is not empty
    empty_slots_stack_top = smc_handler.empty_slots_stack_top()
    assert empty_slots_stack_top == 1
    _, notary_2_pool_index = smc_handler.get_notary_info(notary_2.checksum_address)
    empty_slots = smc_handler.empty_slots_stack(0)
    # Check that the top empty_slots entry point to notary 2
    assert empty_slots == notary_2_pool_index

    notary_4 = TestingNotaryAccount(4)

    # Register notary 4
    smc_handler.register_notary(private_key=notary_4.private_key)
    mine(web3, 1)

    notary_pool_length = smc_handler.notary_pool_len()
    assert notary_pool_length == 4
    # Check that empty_slots_stack is empty
    empty_slots_stack_top = smc_handler.empty_slots_stack_top()
    assert empty_slots_stack_top == 0
    _, notary_4_pool_index = smc_handler.get_notary_info(notary_4.checksum_address)
    # Check that notary fill in notary 2's spot
    assert notary_4_pool_index == notary_2_pool_index
