from eth_tester.backends.pyevm.main import (
    get_default_account_keys,
)


from handler.smc_handler import (
    make_call_context,
)

from tests.handler.fixtures import (  # noqa: F401
    smc_handler,
)
from handler.utils.web3_utils import (
    mine,
)


def test_normal_register(smc_handler):  # noqa: F811
    default_account_keys = get_default_account_keys()
    web3 = smc_handler.web3
    default_gas = smc_handler.config['DEFAULT_GAS']

    collator_0_private_key = default_account_keys[0]
    collator_0_canonical_address = collator_0_private_key.public_key.to_canonical_address()
    collator_0_checksum_address = collator_0_private_key.public_key.to_checksum_address()

    is_collator_exist = smc_handler.call(
        make_call_context(sender_address=collator_0_canonical_address, gas=default_gas)
    ).is_collator_exist(collator_0_checksum_address)
    assert not is_collator_exist
    # Register collator 0
    smc_handler.register_collator(private_key=collator_0_private_key)
    mine(web3, 1)
    is_collator_exist = smc_handler.call(
        make_call_context(sender_address=collator_0_canonical_address, gas=default_gas)
    ).is_collator_exist(collator_0_checksum_address)
    assert is_collator_exist
    collator_deregistered_period, collator_pool_index = smc_handler.call(
        make_call_context(sender_address=collator_0_canonical_address, gas=default_gas)
    ).get_collator_info(collator_0_checksum_address)
    assert collator_deregistered_period == 0 and collator_pool_index == 0
    collator_pool_length = smc_handler.call(
        make_call_context(sender_address=collator_0_canonical_address, gas=default_gas)
    ).collator_pool_len()
    assert collator_pool_length == 1

    collator_1_private_key = default_account_keys[1]
    collator_1_canonical_address = collator_1_private_key.public_key.to_canonical_address()
    collator_1_checksum_address = collator_1_private_key.public_key.to_checksum_address()

    collator_2_private_key = default_account_keys[2]
    collator_2_canonical_address = collator_2_private_key.public_key.to_canonical_address()
    collator_2_checksum_address = collator_2_private_key.public_key.to_checksum_address()

    # Register collator 1 and collator 2
    smc_handler.register_collator(private_key=collator_1_private_key)
    smc_handler.register_collator(private_key=collator_2_private_key)
    mine(web3, 1)

    is_collator_exist = smc_handler.call(
        make_call_context(sender_address=collator_1_canonical_address, gas=default_gas)
    ).is_collator_exist(collator_1_checksum_address)
    assert is_collator_exist
    collator_deregistered_period, collator_pool_index = smc_handler.call(
        make_call_context(sender_address=collator_1_canonical_address, gas=default_gas)
    ).get_collator_info(collator_1_checksum_address)
    assert collator_deregistered_period == 0 and collator_pool_index == 1

    is_collator_exist = smc_handler.call(
        make_call_context(sender_address=collator_2_canonical_address, gas=default_gas)
    ).is_collator_exist(collator_2_checksum_address)
    assert is_collator_exist
    collator_deregistered_period, collator_pool_index = smc_handler.call(
        make_call_context(sender_address=collator_2_canonical_address, gas=default_gas)
    ).get_collator_info(collator_2_checksum_address)
    assert collator_deregistered_period == 0 and collator_pool_index == 2

    collator_pool_length = smc_handler.call(
        make_call_context(sender_address=collator_2_canonical_address, gas=default_gas)
    ).collator_pool_len()
    assert collator_pool_length == 3


def test_register_without_enough_ether(smc_handler):  # noqa: F811
    default_account_keys = get_default_account_keys()
    web3 = smc_handler.web3
    default_gas = smc_handler.config['DEFAULT_GAS']

    collator_0_private_key = default_account_keys[0]
    collator_0_canonical_address = collator_0_private_key.public_key.to_canonical_address()
    collator_0_checksum_address = collator_0_private_key.public_key.to_checksum_address()

    is_collator_exist = smc_handler.call(
        make_call_context(sender_address=collator_0_canonical_address, gas=default_gas)
    ).is_collator_exist(collator_0_checksum_address)
    assert not is_collator_exist

    # Register without enough ether
    smc_handler._send_transaction(
        'register_collator',
        [],
        private_key=collator_0_private_key,
        value=smc_handler.config['COLLATOR_DEPOSIT'] // 10000,
        gas=default_gas,
    )
    mine(web3, 1)

    # Check that the registration failed
    is_collator_exist = smc_handler.call(
        make_call_context(sender_address=collator_0_canonical_address, gas=default_gas)
    ).is_collator_exist(collator_0_checksum_address)
    assert not is_collator_exist
    collator_pool_length = smc_handler.call(
        make_call_context(sender_address=collator_0_canonical_address, gas=default_gas)
    ).collator_pool_len()
    assert collator_pool_length == 0


def test_double_register(smc_handler):  # noqa: F811
    default_account_keys = get_default_account_keys()
    web3 = smc_handler.web3
    default_gas = smc_handler.config['DEFAULT_GAS']

    collator_0_private_key = default_account_keys[0]
    collator_0_canonical_address = collator_0_private_key.public_key.to_canonical_address()
    collator_0_checksum_address = collator_0_private_key.public_key.to_checksum_address()

    # Register collator 0
    smc_handler.register_collator(private_key=collator_0_private_key)
    mine(web3, 1)
    is_collator_exist = smc_handler.call(
        make_call_context(sender_address=collator_0_canonical_address, gas=default_gas)
    ).is_collator_exist(collator_0_checksum_address)
    assert is_collator_exist
    collator_pool_length = smc_handler.call(
        make_call_context(sender_address=collator_0_canonical_address, gas=default_gas)
    ).collator_pool_len()
    assert collator_pool_length == 1

    # Try register collator 0 again
    tx_hash = smc_handler.register_collator(private_key=collator_0_private_key)
    mine(web3, 1)
    # Check pool remain the same and the transaction consume all gas
    collator_pool_length = smc_handler.call(
        make_call_context(sender_address=collator_0_canonical_address, gas=default_gas)
    ).collator_pool_len()
    assert collator_pool_length == 1
    assert web3.eth.getTransactionReceipt(tx_hash)['gasUsed'] == default_gas


def test_normal_deregister(smc_handler):  # noqa: F811
    default_account_keys = get_default_account_keys()
    web3 = smc_handler.web3
    default_gas = smc_handler.config['DEFAULT_GAS']

    collator_0_private_key = default_account_keys[0]
    collator_0_canonical_address = collator_0_private_key.public_key.to_canonical_address()
    collator_0_checksum_address = collator_0_private_key.public_key.to_checksum_address()

    # Register collator 0
    smc_handler.register_collator(private_key=collator_0_private_key)
    mine(web3, 1)
    is_collator_exist = smc_handler.call(
        make_call_context(sender_address=collator_0_canonical_address, gas=default_gas)
    ).is_collator_exist(collator_0_checksum_address)
    assert is_collator_exist
    collator_pool_length = smc_handler.call(
        make_call_context(sender_address=collator_0_canonical_address, gas=default_gas)
    ).collator_pool_len()
    assert collator_pool_length == 1

    # Fast foward
    mine(web3, 100 - web3.eth.blockNumber)

    # Deregister collator 0
    smc_handler.deregister_collator(private_key=collator_0_private_key)
    current_period = web3.eth.blockNumber // smc_handler.config['PERIOD_LENGTH']
    mine(web3, 1)
    is_collator_exist = smc_handler.call(
        make_call_context(sender_address=collator_0_canonical_address, gas=default_gas)
    ).is_collator_exist(collator_0_checksum_address)
    assert is_collator_exist
    collator_deregistered_period, collator_pool_index = smc_handler.call(
        make_call_context(sender_address=collator_0_canonical_address, gas=default_gas)
    ).get_collator_info(collator_0_checksum_address)
    assert collator_deregistered_period == current_period
    collator_pool_length = smc_handler.call(
        make_call_context(sender_address=collator_0_canonical_address, gas=default_gas)
    ).collator_pool_len()
    assert collator_pool_length == 0


def test_deregister_then_register(smc_handler):  # noqa: F811
    default_account_keys = get_default_account_keys()
    web3 = smc_handler.web3
    default_gas = smc_handler.config['DEFAULT_GAS']

    collator_0_private_key = default_account_keys[0]
    collator_0_canonical_address = collator_0_private_key.public_key.to_canonical_address()
    collator_0_checksum_address = collator_0_private_key.public_key.to_checksum_address()

    # Register collator 0
    smc_handler.register_collator(private_key=collator_0_private_key)
    mine(web3, 1)
    is_collator_exist = smc_handler.call(
        make_call_context(sender_address=collator_0_canonical_address, gas=default_gas)
    ).is_collator_exist(collator_0_checksum_address)
    assert is_collator_exist
    collator_pool_length = smc_handler.call(
        make_call_context(sender_address=collator_0_canonical_address, gas=default_gas)
    ).collator_pool_len()
    assert collator_pool_length == 1

    # Fast foward
    mine(web3, 100 - web3.eth.blockNumber)

    # Deregister collator 0
    smc_handler.deregister_collator(private_key=collator_0_private_key)
    current_period = web3.eth.blockNumber // smc_handler.config['PERIOD_LENGTH']
    mine(web3, 1)
    is_collator_exist = smc_handler.call(
        make_call_context(sender_address=collator_0_canonical_address, gas=default_gas)
    ).is_collator_exist(collator_0_checksum_address)
    assert is_collator_exist
    collator_deregistered_period, collator_pool_index = smc_handler.call(
        make_call_context(sender_address=collator_0_canonical_address, gas=default_gas)
    ).get_collator_info(collator_0_checksum_address)
    assert collator_deregistered_period == current_period
    collator_pool_length = smc_handler.call(
        make_call_context(sender_address=collator_0_canonical_address, gas=default_gas)
    ).collator_pool_len()
    assert collator_pool_length == 0

    # Register again right away
    tx_hash = smc_handler.register_collator(private_key=collator_0_private_key)
    mine(web3, 1)
    # Check pool remain the same and the transaction consume all gas
    collator_pool_length = smc_handler.call(
        make_call_context(sender_address=collator_0_canonical_address, gas=default_gas)
    ).collator_pool_len()
    assert collator_pool_length == 0
    assert web3.eth.getTransactionReceipt(tx_hash)['gasUsed'] == default_gas


def test_normal_release_collator(smc_handler):  # noqa: F811
    SIM_COLLATOR_LOCKUP_LENGTH = 120

    default_account_keys = get_default_account_keys()
    web3 = smc_handler.web3
    default_gas = smc_handler.config['DEFAULT_GAS']

    collator_0_private_key = default_account_keys[0]
    collator_0_canonical_address = collator_0_private_key.public_key.to_canonical_address()
    collator_0_checksum_address = collator_0_private_key.public_key.to_checksum_address()

    # Register collator 0
    smc_handler.register_collator(private_key=collator_0_private_key)
    mine(web3, 1)
    is_collator_exist = smc_handler.call(
        make_call_context(sender_address=collator_0_canonical_address, gas=default_gas)
    ).is_collator_exist(collator_0_checksum_address)
    assert is_collator_exist
    collator_pool_length = smc_handler.call(
        make_call_context(sender_address=collator_0_canonical_address, gas=default_gas)
    ).collator_pool_len()
    assert collator_pool_length == 1

    # Fast foward
    mine(web3, 50 - web3.eth.blockNumber)

    # Deregister collator 0
    smc_handler.deregister_collator(private_key=collator_0_private_key)
    mine(web3, 1)
    collator_pool_length = smc_handler.call(
        make_call_context(sender_address=collator_0_canonical_address, gas=default_gas)
    ).collator_pool_len()
    assert collator_pool_length == 0

    # Fast foward
    mine(web3, SIM_COLLATOR_LOCKUP_LENGTH * (smc_handler.config['PERIOD_LENGTH'] + 1))

    # Release collator 0
    smc_handler.release_collator(private_key=collator_0_private_key)
    mine(web3, 1)
    is_collator_exist = smc_handler.call(
        make_call_context(sender_address=collator_0_canonical_address, gas=default_gas)
    ).is_collator_exist(collator_0_checksum_address)
    assert not is_collator_exist


def test_instant_release_collator(smc_handler):  # noqa: F811
    default_account_keys = get_default_account_keys()
    web3 = smc_handler.web3
    default_gas = smc_handler.config['DEFAULT_GAS']

    collator_0_private_key = default_account_keys[0]
    collator_0_canonical_address = collator_0_private_key.public_key.to_canonical_address()
    collator_0_checksum_address = collator_0_private_key.public_key.to_checksum_address()

    # Register collator 0
    smc_handler.register_collator(private_key=collator_0_private_key)
    mine(web3, 1)
    is_collator_exist = smc_handler.call(
        make_call_context(sender_address=collator_0_canonical_address, gas=default_gas)
    ).is_collator_exist(collator_0_checksum_address)
    assert is_collator_exist
    collator_pool_length = smc_handler.call(
        make_call_context(sender_address=collator_0_canonical_address, gas=default_gas)
    ).collator_pool_len()
    assert collator_pool_length == 1

    # Fast foward
    mine(web3, 50 - web3.eth.blockNumber)

    # Deregister collator 0
    smc_handler.deregister_collator(private_key=collator_0_private_key)
    mine(web3, 1)
    collator_pool_length = smc_handler.call(
        make_call_context(sender_address=collator_0_canonical_address, gas=default_gas)
    ).collator_pool_len()
    assert collator_pool_length == 0

    # Instant release collator 0
    tx_hash = smc_handler.release_collator(private_key=collator_0_private_key)
    mine(web3, 1)
    # Check registry remain the same and the transaction consume all gas
    is_collator_exist = smc_handler.call(
        make_call_context(sender_address=collator_0_canonical_address, gas=default_gas)
    ).is_collator_exist(collator_0_checksum_address)
    assert is_collator_exist
    assert web3.eth.getTransactionReceipt(tx_hash)['gasUsed'] == default_gas


def test_deregister_and_new_collator_register(smc_handler):  # noqa: F811
    default_account_keys = get_default_account_keys()
    web3 = smc_handler.web3
    default_gas = smc_handler.config['DEFAULT_GAS']

    collator_0_private_key = default_account_keys[0]
    collator_0_canonical_address = collator_0_private_key.public_key.to_canonical_address()

    # Register collator 0
    smc_handler.register_collator(private_key=collator_0_private_key)
    mine(web3, 1)
    collator_pool_length = smc_handler.call(
        make_call_context(sender_address=collator_0_canonical_address, gas=default_gas)
    ).collator_pool_len()
    assert collator_pool_length == 1

    collator_1_private_key = default_account_keys[1]

    collator_2_private_key = default_account_keys[2]
    collator_2_canonical_address = collator_2_private_key.public_key.to_canonical_address()
    collator_2_checksum_address = collator_2_private_key.public_key.to_checksum_address()

    collator_3_private_key = default_account_keys[3]

    # Register collator 1 and collator 2
    smc_handler.register_collator(private_key=collator_1_private_key)
    smc_handler.register_collator(private_key=collator_2_private_key)
    smc_handler.register_collator(private_key=collator_3_private_key)
    mine(web3, 1)

    collator_pool_length = smc_handler.call(
        make_call_context(sender_address=collator_2_canonical_address, gas=default_gas)
    ).collator_pool_len()
    assert collator_pool_length == 4
    # Check that empty_slots_stack is empty
    empty_slots_stack_top = smc_handler.call(
        make_call_context(sender_address=collator_0_canonical_address, gas=default_gas)
    ).empty_slots_stack_top()
    assert empty_slots_stack_top == 0

    # Fast foward
    mine(web3, 50 - web3.eth.blockNumber)

    # Deregister collator 2
    smc_handler.deregister_collator(private_key=collator_2_private_key)
    mine(web3, 1)
    collator_pool_length = smc_handler.call(
        make_call_context(sender_address=collator_0_canonical_address, gas=default_gas)
    ).collator_pool_len()
    assert collator_pool_length == 3

    # Check that empty_slots_stack is not empty
    empty_slots_stack_top = smc_handler.call(
        make_call_context(sender_address=collator_0_canonical_address, gas=default_gas)
    ).empty_slots_stack_top()
    assert empty_slots_stack_top == 1
    _, collator_2_pool_index = smc_handler.call(
        make_call_context(sender_address=collator_2_canonical_address, gas=default_gas)
    ).get_collator_info(collator_2_checksum_address)
    empty_slots = smc_handler.call(
        make_call_context(sender_address=collator_0_canonical_address, gas=default_gas)
    ).empty_slots_stack(0)
    # Check that the top empty_slots entry point to collator 2
    assert empty_slots == collator_2_pool_index

    collator_4_private_key = default_account_keys[4]
    collator_4_canonical_address = collator_4_private_key.public_key.to_canonical_address()
    collator_4_checksum_address = collator_4_private_key.public_key.to_checksum_address()

    # Register collator 4
    smc_handler.register_collator(private_key=collator_4_private_key)
    mine(web3, 1)

    collator_pool_length = smc_handler.call(
        make_call_context(sender_address=collator_0_canonical_address, gas=default_gas)
    ).collator_pool_len()
    assert collator_pool_length == 4
    # Check that empty_slots_stack is empty
    empty_slots_stack_top = smc_handler.call(
        make_call_context(sender_address=collator_0_canonical_address, gas=default_gas)
    ).empty_slots_stack_top()
    assert empty_slots_stack_top == 0
    _, collator_4_pool_index = smc_handler.call(
        make_call_context(sender_address=collator_4_canonical_address, gas=default_gas)
    ).get_collator_info(collator_4_checksum_address)
    # Check that collator fill in collator 2's spot
    assert collator_4_pool_index == collator_2_pool_index
