from sharding.handler.log_handler import (  # noqa: F401
    LogHandler,
)
from sharding.handler.shard_tracker import (  # noqa: F401
    ShardTracker,
)
from sharding.handler.utils.web3_utils import (
    mine,
)
from tests.handler.fixtures import (  # noqa: F401
    smc_handler,
)
from tests.contract.utils.common_utils import (
    fast_forward,
)
from tests.contract.utils.notary_account import (
    NotaryAccount,
)
from tests.contract.utils.sample_helper import (
    sampling,
)
from tests.handler.utils.config import (
    get_sharding_testing_config,
)


def test_log_emission(smc_handler):  # noqa: F811
    web3 = smc_handler.web3
    config = get_sharding_testing_config()
    log_handler = LogHandler(web3=web3, period_length=config['PERIOD_LENGTH'])
    shard_tracker = ShardTracker(
        config=config,
        shard_id=0,
        log_handler=log_handler,
        smc_handler_address=smc_handler.address,
    )
    notary = NotaryAccount(0)

    # Register
    smc_handler.register_notary(private_key=notary.private_key)
    mine(web3, 1)
    # Check that log was successfully emitted
    log = shard_tracker.get_register_notary_logs()[0]
    assert log['index_in_notary_pool'] == 0 and log['notary'] == notary.checksum_address
    fast_forward(smc_handler, 1)

    # Add header
    CHUNK_ROOT_1_0 = b'\x10' * 32
    smc_handler.add_header(
        period=1,
        shard_id=0,
        chunk_root=CHUNK_ROOT_1_0,
        private_key=notary.private_key
    )
    mine(web3, 1)
    # Check that log was successfully emitted
    log = shard_tracker.get_add_header_logs()[0]
    assert log['period'] == 1 and log['shard_id'] == 0 and log['chunk_root'] == CHUNK_ROOT_1_0

    # Submit vote
    sample_index = 0
    pool_index = sampling(smc_handler, 0)[sample_index]
    smc_handler.submit_vote(
        period=1,
        shard_id=0,
        chunk_root=CHUNK_ROOT_1_0,
        index=sample_index,
        private_key=NotaryAccount(pool_index).private_key
    )
    mine(web3, 1)
    # Check that log was successfully emitted
    log = shard_tracker.get_submit_vote_logs()[0]
    assert log['period'] == 1 and log['shard_id'] == 0 and log['chunk_root'] == CHUNK_ROOT_1_0 \
        and log['notary'] == NotaryAccount(pool_index).checksum_address
    fast_forward(smc_handler, 1)

    # Deregister
    smc_handler.deregister_notary(private_key=notary.private_key)
    mine(web3, 1)
    # Check that log was successfully emitted
    log = shard_tracker.get_deregister_notary_logs()[0]
    assert log['index_in_notary_pool'] == 0 and log['notary'] == notary.checksum_address \
        and log['deregistered_period'] == 2
    # Fast foward to end of lock up
    fast_forward(smc_handler, smc_handler.config['NOTARY_LOCKUP_LENGTH'] + 1)

    # Release
    smc_handler.release_notary(private_key=notary.private_key)
    mine(web3, 1)
    # Check that log was successfully emitted
    log = shard_tracker.get_release_notary_logs()[0]
    assert log['index_in_notary_pool'] == 0 and log['notary'] == notary.checksum_address
