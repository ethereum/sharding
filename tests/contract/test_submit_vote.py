import pytest

from sharding.handler.utils.web3_utils import (
    mine,
)

from tests.contract.utils.common_utils import (
    batch_register,
    fast_forward,
)
from tests.contract.utils.notary_account import (
    NotaryAccount,
)
from tests.contract.utils.sample_helper import (
    sampling,
    get_sample_result,
)


def test_normal_submit_vote(smc_handler):  # noqa: F811
    w3 = smc_handler.web3
    # We only vote in shard 0 for ease of testing
    shard_id = 0

    # Register notary 0~8 and fast forward to next period
    batch_register(smc_handler, 0, 8)
    fast_forward(smc_handler, 1)
    current_period = w3.eth.blockNumber // smc_handler.config['PERIOD_LENGTH']
    assert current_period == 1

    # Add collation record
    CHUNK_ROOT_1_0 = b'\x10' * 32
    smc_handler.add_header(
        shard_id=shard_id,
        period=current_period,
        chunk_root=CHUNK_ROOT_1_0,
        private_key=NotaryAccount(index=0).private_key,
    )
    mine(w3, 1)

    # Get the first notary in the sample list in this period
    sample_index = 0
    pool_index = sampling(smc_handler, shard_id)[sample_index]
    # Check that voting record does not exist prior to voting
    assert smc_handler.get_vote_count(shard_id) == 0
    assert not smc_handler.has_notary_voted(shard_id, sample_index)
    # First notary vote
    smc_handler.submit_vote(
        shard_id=shard_id,
        period=current_period,
        chunk_root=CHUNK_ROOT_1_0,
        index=sample_index,
        private_key=NotaryAccount(index=pool_index).private_key,
    )
    mine(w3, 1)
    # Check that vote has been casted successfully
    assert smc_handler.get_vote_count(shard_id) == 1
    assert smc_handler.has_notary_voted(shard_id, sample_index)

    # Check that collation is not elected and forward to next period
    assert not smc_handler.get_collation_is_elected(shard_id=shard_id, period=current_period)
    fast_forward(smc_handler, 1)
    current_period = w3.eth.blockNumber // smc_handler.config['PERIOD_LENGTH']
    assert current_period == 2

    # Add collation record
    CHUNK_ROOT_2_0 = b'\x20' * 32
    smc_handler.add_header(
        shard_id=shard_id,
        period=current_period,
        chunk_root=CHUNK_ROOT_2_0,
        private_key=NotaryAccount(index=0).private_key,
    )
    mine(w3, 1)

    # Check that vote count is zero
    assert smc_handler.get_vote_count(shard_id) == 0
    # Keep voting until the collation is elected.
    for (sample_index, pool_index) in enumerate(sampling(smc_handler, shard_id)):
        if smc_handler.get_collation_is_elected(shard_id=shard_id, period=current_period):
            assert smc_handler.get_vote_count(shard_id) == smc_handler.config['QUORUM_SIZE']
            break
        # Check that voting record does not exist prior to voting
        assert not smc_handler.has_notary_voted(shard_id, sample_index)
        # Vote
        smc_handler.submit_vote(
            shard_id=shard_id,
            period=current_period,
            chunk_root=CHUNK_ROOT_2_0,
            index=sample_index,
            private_key=NotaryAccount(index=pool_index).private_key,
        )
        mine(w3, 1)
        # Check that vote has been casted successfully
        assert smc_handler.has_notary_voted(shard_id, sample_index)
    # Check that the collation is indeed elected.
    assert smc_handler.get_collation_is_elected(shard_id=shard_id, period=current_period)


def test_double_submit_vote(smc_handler):  # noqa: F811
    w3 = smc_handler.web3
    # We only vote in shard 0 for ease of testing
    shard_id = 0

    # Register notary 0~8 and fast forward to next period
    batch_register(smc_handler, 0, 8)
    fast_forward(smc_handler, 1)
    current_period = w3.eth.blockNumber // smc_handler.config['PERIOD_LENGTH']
    assert current_period == 1

    # Add collation record
    CHUNK_ROOT_1_0 = b'\x10' * 32
    smc_handler.add_header(
        shard_id=shard_id,
        period=current_period,
        chunk_root=CHUNK_ROOT_1_0,
        private_key=NotaryAccount(index=0).private_key,
    )
    mine(w3, 1)

    # Get the first notary in the sample list in this period and vote
    sample_index = 0
    pool_index = sampling(smc_handler, shard_id)[sample_index]
    smc_handler.submit_vote(
        shard_id=shard_id,
        period=current_period,
        chunk_root=CHUNK_ROOT_1_0,
        index=sample_index,
        private_key=NotaryAccount(index=pool_index).private_key,
    )
    mine(w3, 1)
    # Check that vote has been casted successfully
    assert smc_handler.get_vote_count(shard_id) == 1
    assert smc_handler.has_notary_voted(shard_id, sample_index)

    # Attempt to double vote
    tx_hash = smc_handler.submit_vote(
        shard_id=shard_id,
        period=current_period,
        chunk_root=CHUNK_ROOT_1_0,
        index=sample_index,
        private_key=NotaryAccount(index=pool_index).private_key,
    )
    mine(w3, 1)
    # Check that transaction failed and vote count remains the same
    # and no logs has been emitted
    assert len(w3.eth.getTransactionReceipt(tx_hash)['logs']) == 0
    assert smc_handler.get_vote_count(shard_id) == 1


def test_submit_vote_by_notary_sampled_multiple_times(smc_handler):  # noqa: F811
    w3 = smc_handler.web3
    # We only vote in shard 0 for ease of testing
    shard_id = 0

    # Here we only register 5 notaries so it's guaranteed that at least
    # one notary is going to be sampled twice.
    # Register notary 0~4 and fast forward to next period
    batch_register(smc_handler, 0, 4)
    fast_forward(smc_handler, 1)
    current_period = w3.eth.blockNumber // smc_handler.config['PERIOD_LENGTH']
    assert current_period == 1

    # Add collation record
    CHUNK_ROOT_1_0 = b'\x10' * 32
    smc_handler.add_header(
        shard_id=shard_id,
        period=current_period,
        chunk_root=CHUNK_ROOT_1_0,
        private_key=NotaryAccount(index=0).private_key,
    )
    mine(w3, 1)

    # Find the notary that's sampled more than one time
    for pool_index in range(5):
        sample_index_list = [
            sample_index
            for (_, _shard_id, sample_index) in get_sample_result(smc_handler, pool_index)
            if _shard_id == shard_id
        ]
        if len(sample_index_list) > 1:
            vote_count = len(sample_index_list)
            for sample_index in sample_index_list:
                smc_handler.submit_vote(
                    shard_id=shard_id,
                    period=current_period,
                    chunk_root=CHUNK_ROOT_1_0,
                    index=sample_index,
                    private_key=NotaryAccount(index=pool_index).private_key,
                )
                mine(w3, 1)
            # Check that every vote is successfully casted even by the same notary
            assert smc_handler.get_vote_count(shard_id) == vote_count
            break


def test_submit_vote_by_non_eligible_notary(smc_handler):  # noqa: F811
    w3 = smc_handler.web3
    # We only vote in shard 0 for ease of testing
    shard_id = 0

    # Register notary 0~8 and fast forward to next period
    batch_register(smc_handler, 0, 8)
    fast_forward(smc_handler, 1)
    current_period = w3.eth.blockNumber // smc_handler.config['PERIOD_LENGTH']
    assert current_period == 1

    # Add collation record
    CHUNK_ROOT_1_0 = b'\x10' * 32
    smc_handler.add_header(
        shard_id=shard_id,
        period=current_period,
        chunk_root=CHUNK_ROOT_1_0,
        private_key=NotaryAccount(index=0).private_key,
    )
    mine(w3, 1)

    sample_index = 0
    pool_index = sampling(smc_handler, shard_id)[sample_index]
    wrong_pool_index = 0 if pool_index != 0 else 1
    tx_hash = smc_handler.submit_vote(
        shard_id=shard_id,
        period=current_period,
        chunk_root=CHUNK_ROOT_1_0,
        index=sample_index,
        # Vote by non-eligible notary
        private_key=NotaryAccount(wrong_pool_index).private_key,
    )
    mine(w3, 1)
    # Check that transaction failed and vote count remains the same
    # and no logs has been emitted
    assert len(w3.eth.getTransactionReceipt(tx_hash)['logs']) == 0
    assert smc_handler.get_vote_count(shard_id) == 0
    assert not smc_handler.has_notary_voted(shard_id, sample_index)


def test_submit_vote_without_add_header_first(smc_handler):  # noqa: F811
    w3 = smc_handler.web3
    # We only vote in shard 0 for ease of testing
    shard_id = 0

    # Register notary 0~8 and fast forward to next period
    batch_register(smc_handler, 0, 8)
    fast_forward(smc_handler, 1)
    current_period = w3.eth.blockNumber // smc_handler.config['PERIOD_LENGTH']
    assert current_period == 1

    CHUNK_ROOT_1_0 = b'\x10' * 32
    # Get the first notary in the sample list in this period and vote
    sample_index = 0
    pool_index = sampling(smc_handler, shard_id)[sample_index]
    tx_hash = smc_handler.submit_vote(
        shard_id=shard_id,
        period=current_period,
        chunk_root=CHUNK_ROOT_1_0,
        index=sample_index,
        private_key=NotaryAccount(index=pool_index).private_key,
    )
    mine(w3, 1)
    # Check that transaction failed and vote count remains the same
    # and no logs has been emitted
    assert len(w3.eth.getTransactionReceipt(tx_hash)['logs']) == 0
    assert smc_handler.get_vote_count(shard_id) == 0
    assert not smc_handler.has_notary_voted(shard_id, sample_index)


@pytest.mark.parametrize(  # noqa: F811
    'period, shard_id, chunk_root, sample_index',
    (
        (-1, 0, b'\x10' * 32, 0),
        (999, 0, b'\x10' * 32, 0),
        (1, -1, b'\x10' * 32, 0),
        (1, 999, b'\x10' * 32, 0),
        (1, 0, b'\xff' * 32, 0),
        (1, 0, b'\x10' * 32, -1),
        (1, 0, b'\x10' * 32, 999),
    )
)
def test_submit_vote_with_invalid_args(smc_handler, period, shard_id, chunk_root, sample_index):
    w3 = smc_handler.web3

    # Register notary 0~8 and fast forward to next period
    batch_register(smc_handler, 0, 8)
    fast_forward(smc_handler, 1)
    current_period = w3.eth.blockNumber // smc_handler.config['PERIOD_LENGTH']
    assert current_period == 1

    # Add correct collation record
    smc_handler.add_header(
        shard_id=0,
        period=current_period,
        chunk_root=b'\x10' * 32,
        private_key=NotaryAccount(index=0).private_key,
    )
    mine(w3, 1)

    pool_index = sampling(smc_handler, 0)[0]
    # Vote with provided incorrect arguments
    tx_hash = smc_handler.submit_vote(
        shard_id=shard_id,
        period=period,
        chunk_root=chunk_root,
        index=sample_index,
        private_key=NotaryAccount(index=pool_index).private_key,
    )
    mine(w3, 1)
    # Check that transaction failed and vote count remains the same
    # and no logs has been emitted
    assert len(w3.eth.getTransactionReceipt(tx_hash)['logs']) == 0
    assert smc_handler.get_vote_count(shard_id) == 0
    assert not smc_handler.has_notary_voted(shard_id, sample_index)


def test_submit_vote_then_deregister(smc_handler):  # noqa: F811
    w3 = smc_handler.web3
    # We only vote in shard 0 for ease of testing
    shard_id = 0

    # Register notary 0~8 and fast forward to next period
    batch_register(smc_handler, 0, 8)
    fast_forward(smc_handler, 1)
    current_period = w3.eth.blockNumber // smc_handler.config['PERIOD_LENGTH']
    assert current_period == 1

    # Add collation record
    CHUNK_ROOT_1_0 = b'\x10' * 32
    smc_handler.add_header(
        shard_id=shard_id,
        period=current_period,
        chunk_root=CHUNK_ROOT_1_0,
        private_key=NotaryAccount(index=0).private_key,
    )
    mine(w3, 1)

    sample_index = 0
    pool_index = sampling(smc_handler, shard_id)[sample_index]
    smc_handler.submit_vote(
        shard_id=shard_id,
        period=current_period,
        chunk_root=CHUNK_ROOT_1_0,
        index=sample_index,
        private_key=NotaryAccount(index=pool_index).private_key,
    )
    mine(w3, 1)

    # Check that vote has been casted successfully
    assert smc_handler.get_vote_count(shard_id) == 1
    assert smc_handler.has_notary_voted(shard_id, sample_index)

    # The notary deregisters
    smc_handler.deregister_notary(private_key=NotaryAccount(pool_index).private_key)
    mine(w3, 1)
    # Check that vote was not effected by deregistration
    assert smc_handler.get_vote_count(shard_id) == 1
    assert smc_handler.has_notary_voted(shard_id, sample_index)

    # Notary 9 registers and takes retired notary's place in pool
    smc_handler.register_notary(private_key=NotaryAccount(9).private_key)
    # Attempt to vote
    tx_hash = smc_handler.submit_vote(
        shard_id=shard_id,
        period=current_period,
        chunk_root=CHUNK_ROOT_1_0,
        index=sample_index,
        private_key=NotaryAccount(index=9).private_key,
    )
    mine(w3, 1)

    # Check that transaction failed and vote count remains the same
    # and no logs has been emitted
    assert len(w3.eth.getTransactionReceipt(tx_hash)['logs']) == 0
    assert smc_handler.get_vote_count(shard_id) == 1
