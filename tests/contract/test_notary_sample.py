from handler.utils.web3_utils import (
    mine,
)
from tests.handler.fixtures import (  # noqa: F401
    smc_handler,
)
from tests.contract.utils.common_utils import (
    update_notary_sample_size,
    batch_register,
    fast_forward,
)
from tests.contract.utils.notary_account import (
    TestingNotaryAccount,
)
from tests.contract.utils.sample_helper import (
    get_notary_pool_list,
    get_committee_list,
    get_sample_result,
)


def test_normal_update_notary_sample_size(smc_handler):  # noqa: F811
    web3 = smc_handler.web3

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

    # Try updating notary sample size
    update_notary_sample_size(smc_handler)
    # Check that current_period_notary_sample_size is not updated,
    # i.e., updating notary sample size failed.
    assert 0 == current_period_notary_sample_size

    # fast forward to next period
    fast_forward(smc_handler, 1)

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
    fast_forward(smc_handler, 1)

    # Deregister notary 0 first
    # NOTE: Deregistration would also invoke update_notary_sample_size function
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

    notary_0 = TestingNotaryAccount(0)
    notary_1 = TestingNotaryAccount(1)
    notary_2 = TestingNotaryAccount(2)

    # Register notary 0~2
    batch_register(smc_handler, 0, 2)
    next_period_notary_sample_size = smc_handler.next_period_notary_sample_size()
    assert next_period_notary_sample_size == 3

    # Fast forward to next period
    fast_forward(smc_handler, 1)

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
    fast_forward(smc_handler, 1)

    # Update notary sample size
    update_notary_sample_size(smc_handler)
    current_period_notary_sample_size = smc_handler.current_period_notary_sample_size()
    assert current_period_notary_sample_size == next_period_notary_sample_size


def test_series_of_deregister_starting_from_bottom_of_the_stack(smc_handler):  # noqa: F811
    web3 = smc_handler.web3

    notary_0 = TestingNotaryAccount(0)
    notary_1 = TestingNotaryAccount(1)
    notary_2 = TestingNotaryAccount(2)

    # Register notary 0~2
    batch_register(smc_handler, 0, 2)

    # Fast forward to next period
    fast_forward(smc_handler, 1)

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
    fast_forward(smc_handler, 1)

    # Update notary sample size
    update_notary_sample_size(smc_handler)
    current_period_notary_sample_size = smc_handler.current_period_notary_sample_size()
    assert current_period_notary_sample_size == next_period_notary_sample_size


def test_get_member_of_committee_without_updating_sample_size(smc_handler):  # noqa: F811
    web3 = smc_handler.web3

    # Register notary 0~5 and fast forward to next period
    batch_register(smc_handler, 0, 5)
    fast_forward(smc_handler, 1)

    # Register notary 6~8
    batch_register(smc_handler, 6, 8)

    # Check that sample-size-related values match
    current_period = web3.eth.blockNumber // smc_handler.config['PERIOD_LENGTH']
    notary_sample_size_updated_period = smc_handler.notary_sample_size_updated_period()
    assert notary_sample_size_updated_period == current_period
    current_period_notary_sample_size = smc_handler.current_period_notary_sample_size()
    assert current_period_notary_sample_size == 6
    next_period_notary_sample_size = smc_handler.next_period_notary_sample_size()
    assert next_period_notary_sample_size == 9

    # Fast forward to next period
    fast_forward(smc_handler, 1)
    current_period = web3.eth.blockNumber // smc_handler.config['PERIOD_LENGTH']
    notary_sample_size_updated_period = smc_handler.notary_sample_size_updated_period()
    assert notary_sample_size_updated_period == current_period - 1

    shard_0_committee_list = get_committee_list(smc_handler, 0)
    for (i, notary) in enumerate(shard_0_committee_list):
        assert smc_handler.get_member_of_committee(0, i) == notary


def test_get_member_of_committee_with_updated_sample_size(smc_handler):  # noqa: F811
    web3 = smc_handler.web3

    # Register notary 0~8 and fast forward to next period
    batch_register(smc_handler, 0, 8)
    fast_forward(smc_handler, 1)

    # Update notary sample size
    update_notary_sample_size(smc_handler)
    # Check that sample-size-related values match
    current_period = web3.eth.blockNumber // smc_handler.config['PERIOD_LENGTH']
    notary_sample_size_updated_period = smc_handler.notary_sample_size_updated_period()
    assert notary_sample_size_updated_period == current_period
    current_period_notary_sample_size = smc_handler.current_period_notary_sample_size()
    assert current_period_notary_sample_size == 9
    next_period_notary_sample_size = smc_handler.next_period_notary_sample_size()
    assert next_period_notary_sample_size == 9

    shard_0_committee_list = get_committee_list(smc_handler, 0)
    for (i, notary) in enumerate(shard_0_committee_list):
        assert smc_handler.get_member_of_committee(0, i) == notary


def test_committee_lists_generated_are_different(smc_handler):  # noqa: F811
    # Register notary 0~8 and fast forward to next period
    batch_register(smc_handler, 0, 8)
    fast_forward(smc_handler, 1)

    # Update notary sample size
    update_notary_sample_size(smc_handler)

    shard_0_committee_list = get_committee_list(smc_handler, 0)
    shard_1_committee_list = get_committee_list(smc_handler, 1)
    assert shard_0_committee_list != shard_1_committee_list

    # Fast forward to next period
    fast_forward(smc_handler, 1)

    # Update notary sample size
    update_notary_sample_size(smc_handler)

    new_shard_0_committee_list = get_committee_list(smc_handler, 0)
    assert new_shard_0_committee_list != shard_0_committee_list


def test_get_member_of_committee_with_non_member(smc_handler):  # noqa: F811
    # Register notary 0~8 and fast forward to next period
    batch_register(smc_handler, 0, 8)
    fast_forward(smc_handler, 1)

    # Update notary sample size
    update_notary_sample_size(smc_handler)

    notary_pool_list = get_notary_pool_list(smc_handler)
    shard_0_committee_list = get_committee_list(smc_handler, 0)
    for (i, notary) in enumerate(shard_0_committee_list):
        notary_index = notary_pool_list.index(notary)
        next_notary_index = notary_index + 1 \
            if notary_index < len(notary_pool_list) - 1 else 0
        next_notary = notary_pool_list[next_notary_index]
        assert not (smc_handler.get_member_of_committee(0, i) == next_notary)


def test_get_member_of_committee_with_deregistered_notary(smc_handler):  # noqa: F811
    web3 = smc_handler.web3

    # Register notary 0~8 and fast forward to next period
    batch_register(smc_handler, 0, 8)
    fast_forward(smc_handler, 1)

    # Update notary sample size
    update_notary_sample_size(smc_handler)

    notary_pool_list = get_notary_pool_list(smc_handler)
    # Choose the first sampled notary and deregister it
    notary = get_committee_list(smc_handler, 0)[0]
    notary_index = notary_pool_list.index(notary)
    smc_handler.deregister_notary(private_key=TestingNotaryAccount(notary_index).private_key)
    mine(web3, 1)
    assert not (smc_handler.get_member_of_committee(0, 0) == notary_pool_list[notary_index])


def test_get_sample_result(smc_handler):  # noqa: F811
    # Register notary 0~8 and fast forward to next period
    batch_register(smc_handler, 0, 8)
    fast_forward(smc_handler, 1)

    # Update notary sample size
    update_notary_sample_size(smc_handler)

    # Get all committee of current period
    committee_group = []
    for shard_id in range(smc_handler.config['SHARD_COUNT']):
        committee_group.append(get_committee_list(smc_handler, shard_id))

    # Get sampling result for notary 0
    notary_0 = TestingNotaryAccount(0)
    _, notary_0_pool_index = smc_handler.get_notary_info(
        notary_0.checksum_address
    )
    notary_0_sampling_result = get_sample_result(smc_handler, notary_0_pool_index)

    for (shard_id, sampling_index) in notary_0_sampling_result:
        # Check that notary is correctly sampled in get_committee_list
        assert committee_group[shard_id][sampling_index] == notary_0.checksum_address
        # Check that notary is correctly sampled in SMC
        assert smc_handler.get_member_of_committee(shard_id, sampling_index) \
            == notary_0.checksum_address
