from handler.utils.web3_utils import (
    mine,
)
from tests.handler.fixtures import (  # noqa: F401
    smc_handler,
)
from tests.contract.utils.notary_account import (
    TestingNotaryAccount,
)


def test_normal_update_notary_sample_size(smc_handler):  # noqa: F811
    web3 = smc_handler.web3
    default_gas = smc_handler.config['DEFAULT_GAS']

    notary_0 = TestingNotaryAccount(0)

    # Register notary 0
    smc_handler.register_notary(private_key=notary_0.private_key)
    mine(web3, 1)
    _, notary_0_pool_index = smc_handler.get_notary_info(
        notary_0.checksum_address
    )
    assert notary_0_pool_index == 0
    next_period_notary_sample_size = smc_handler.next_period_notary_sample_size()
    assert (notary_0_pool_index + 1) == next_period_notary_sample_size

    notary_1 = TestingNotaryAccount(1)

    # Register notary 1
    smc_handler.register_notary(private_key=notary_1.private_key)
    mine(web3, 1)

    _, notary_1_pool_index = smc_handler.get_notary_info(
        notary_1.checksum_address
    )
    assert notary_1_pool_index == 1
    next_period_notary_sample_size = smc_handler.next_period_notary_sample_size()
    assert (notary_1_pool_index + 1) == next_period_notary_sample_size

    # Check that it's not yet the time to update notary sample size,
    # i.e., current period is the same as latest period the notary sample size was updated.
    current_period = web3.eth.blockNumber // smc_handler.config['PERIOD_LENGTH']
    notary_sample_size_updated_period = smc_handler.notary_sample_size_updated_period()
    assert current_period == notary_sample_size_updated_period

    # Check that current_period_notary_sample_size has not been updated before
    current_period_notary_sample_size = smc_handler.current_period_notary_sample_size()
    assert 0 == current_period_notary_sample_size

    # Try updating sample size
    smc_handler._send_transaction(
        'update_notary_sample_size',
        [],
        private_key=notary_0.private_key,
        gas=default_gas,
    )
    mine(web3, 1)
    # Check that current_period_notary_sample_size is not updated,
    # i.e., updating sample size failed.
    assert 0 == current_period_notary_sample_size

    # fast forward to next period
    blocks_to_next_period = (current_period + 1) * smc_handler.config['PERIOD_LENGTH'] \
        - web3.eth.blockNumber
    mine(web3, blocks_to_next_period)

    # Register notary 2
    # NOTE: Registration would also invoke update_notary_sample_size function
    notary_2 = TestingNotaryAccount(2)
    smc_handler.register_notary(private_key=notary_2.private_key)
    mine(web3, 1)

    # Check that current_period_notary_sample_size is updated,
    # i.e., it is assigned the value of next_period_notary_sample_size.
    current_period_notary_sample_size = smc_handler.current_period_notary_sample_size()
    assert next_period_notary_sample_size == current_period_notary_sample_size

    # Check that notary sample size is updated in this period
    current_period = web3.eth.blockNumber // smc_handler.config['PERIOD_LENGTH']
    notary_sample_size_updated_period = smc_handler.notary_sample_size_updated_period()
    assert current_period == notary_sample_size_updated_period


def test_register_then_deregister(smc_handler):  # noqa: F811
    web3 = smc_handler.web3

    notary_0 = TestingNotaryAccount(0)

    # Register notary 0 first
    smc_handler.register_notary(private_key=notary_0.private_key)
    mine(web3, 1)
    _, notary_0_pool_index = smc_handler.get_notary_info(
        notary_0.checksum_address
    )
    assert notary_0_pool_index == 0
    next_period_notary_sample_size = smc_handler.next_period_notary_sample_size()
    assert (notary_0_pool_index + 1) == next_period_notary_sample_size

    # Then deregister notary 0
    smc_handler.deregister_notary(private_key=notary_0.private_key)
    mine(web3, 1)
    # Check that next_period_notary_sample_size remains the same
    next_period_notary_sample_size = smc_handler.next_period_notary_sample_size()
    assert (notary_0_pool_index + 1) == next_period_notary_sample_size


def test_deregister_then_register(smc_handler):  # noqa: F811
    web3 = smc_handler.web3

    notary_0 = TestingNotaryAccount(0)

    # Register notary 0 and fast forward to next period
    smc_handler.register_notary(private_key=notary_0.private_key)
    current_period = web3.eth.blockNumber // smc_handler.config['PERIOD_LENGTH']
    blocks_to_next_period = (current_period + 1) * smc_handler.config['PERIOD_LENGTH'] \
        - web3.eth.blockNumber
    mine(web3, blocks_to_next_period)

    # Deregister notary 0 first
    # NOTE: Deregitration would also invoke update_notary_sample_size function
    smc_handler.deregister_notary(private_key=notary_0.private_key)
    mine(web3, 1)
    # Check that current_period_notary_sample_size is updated
    current_period_notary_sample_size = smc_handler.current_period_notary_sample_size()
    assert current_period_notary_sample_size == 1

    notary_1 = TestingNotaryAccount(1)

    # Then register notary 1
    smc_handler.register_notary(private_key=notary_1.private_key)
    mine(web3, 1)

    _, notary_1_pool_index = smc_handler.get_notary_info(
        notary_1.checksum_address
    )
    assert notary_1_pool_index == 0
    # Check that next_period_notary_sample_size remains the same
    next_period_notary_sample_size = smc_handler.next_period_notary_sample_size()
    assert (notary_1_pool_index + 1) == next_period_notary_sample_size


def test_series_of_deregister_starting_from_top_of_the_stack(smc_handler):  # noqa: F811
    web3 = smc_handler.web3
    default_gas = smc_handler.config['DEFAULT_GAS']

    notary_0 = TestingNotaryAccount(0)
    notary_1 = TestingNotaryAccount(1)
    notary_2 = TestingNotaryAccount(2)

    # Register notary 0~2
    smc_handler.register_notary(private_key=notary_0.private_key)
    smc_handler.register_notary(private_key=notary_1.private_key)
    smc_handler.register_notary(private_key=notary_2.private_key)
    mine(web3, 1)
    next_period_notary_sample_size = smc_handler.next_period_notary_sample_size()
    assert next_period_notary_sample_size == 3

    # Fast forward to next period
    current_period = web3.eth.blockNumber // smc_handler.config['PERIOD_LENGTH']
    blocks_to_next_period = (current_period + 1) * smc_handler.config['PERIOD_LENGTH'] \
        - web3.eth.blockNumber
    mine(web3, blocks_to_next_period)

    # Deregister from notary 2 to notary 0
    # Deregister notary 2
    smc_handler.deregister_notary(private_key=notary_2.private_key)
    mine(web3, 1)
    # Check that current_period_notary_sample_size is updated
    current_period_notary_sample_size = smc_handler.current_period_notary_sample_size()
    assert current_period_notary_sample_size == 3
    # Check that next_period_notary_sample_size remains the samev
    next_period_notary_sample_size = smc_handler.next_period_notary_sample_size()
    assert next_period_notary_sample_size == 3
    # Deregister notary 1
    smc_handler.deregister_notary(private_key=notary_1.private_key)
    mine(web3, 1)
    # Check that next_period_notary_sample_size remains the same
    next_period_notary_sample_size = smc_handler.next_period_notary_sample_size()
    assert next_period_notary_sample_size == 3
    # Deregister notary 0
    smc_handler.deregister_notary(private_key=notary_0.private_key)
    mine(web3, 1)
    # Check that next_period_notary_sample_size remains the same
    next_period_notary_sample_size = smc_handler.next_period_notary_sample_size()
    assert next_period_notary_sample_size == 3

    # Fast forward to next period
    current_period = web3.eth.blockNumber // smc_handler.config['PERIOD_LENGTH']
    blocks_to_next_period = (current_period + 1) * smc_handler.config['PERIOD_LENGTH'] \
        - web3.eth.blockNumber
    mine(web3, blocks_to_next_period)

    # Update notary sample size
    smc_handler._send_transaction(
        'update_notary_sample_size',
        [],
        private_key=notary_0.private_key,
        gas=default_gas,
    )
    mine(web3, 1)
    current_period_notary_sample_size = smc_handler.current_period_notary_sample_size()
    assert current_period_notary_sample_size == next_period_notary_sample_size


def test_series_of_deregister_starting_from_bottom_of_the_stack(smc_handler):  # noqa: F811
    web3 = smc_handler.web3
    default_gas = smc_handler.config['DEFAULT_GAS']

    notary_0 = TestingNotaryAccount(0)
    notary_1 = TestingNotaryAccount(1)
    notary_2 = TestingNotaryAccount(2)

    # Register notary 0~2
    smc_handler.register_notary(private_key=notary_0.private_key)
    smc_handler.register_notary(private_key=notary_1.private_key)
    smc_handler.register_notary(private_key=notary_2.private_key)
    mine(web3, 1)

    # Fast forward to next period
    current_period = web3.eth.blockNumber // smc_handler.config['PERIOD_LENGTH']
    blocks_to_next_period = (current_period + 1) * smc_handler.config['PERIOD_LENGTH'] \
        - web3.eth.blockNumber
    mine(web3, blocks_to_next_period)

    # Deregister from notary 0 to notary 2
    # Deregister notary 0
    smc_handler.deregister_notary(private_key=notary_0.private_key)
    mine(web3, 1)
    _, notary_0_pool_index = smc_handler.get_notary_info(
        notary_0.checksum_address
    )
    next_period_notary_sample_size = smc_handler.next_period_notary_sample_size()
    # Check that next_period_notary_sample_size remains the same
    assert next_period_notary_sample_size == 3
    # Deregister notary 1
    smc_handler.deregister_notary(private_key=notary_1.private_key)
    mine(web3, 1)
    _, notary_1_pool_index = smc_handler.get_notary_info(
        notary_1.checksum_address
    )
    next_period_notary_sample_size = smc_handler.next_period_notary_sample_size()
    # Check that next_period_notary_sample_size remains the same
    assert next_period_notary_sample_size == 3
    # Deregister notary 2
    smc_handler.deregister_notary(private_key=notary_2.private_key)
    mine(web3, 1)
    # Check that current_period_notary_sample_size is updated
    current_period_notary_sample_size = smc_handler.current_period_notary_sample_size()
    assert current_period_notary_sample_size == 3
    _, notary_2_pool_index = smc_handler.get_notary_info(
        notary_2.checksum_address
    )
    next_period_notary_sample_size = smc_handler.next_period_notary_sample_size()
    assert next_period_notary_sample_size == 3

    # Fast forward to next period
    current_period = web3.eth.blockNumber // smc_handler.config['PERIOD_LENGTH']
    blocks_to_next_period = (current_period + 1) * smc_handler.config['PERIOD_LENGTH'] \
        - web3.eth.blockNumber
    mine(web3, blocks_to_next_period)

    # Update notary sample size
    smc_handler._send_transaction(
        'update_notary_sample_size',
        [],
        private_key=notary_0.private_key,
        gas=default_gas,
    )
    mine(web3, 1)
    current_period_notary_sample_size = smc_handler.current_period_notary_sample_size()
    assert current_period_notary_sample_size == next_period_notary_sample_size
