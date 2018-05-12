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


def test_log_emission(smc_handler):  # noqa: F811
    web3 = smc_handler.web3
    notary = NotaryAccount(0)

    # Register
    tx_hash = smc_handler.register_notary(private_key=notary.private_key)
    mine(web3, 1)
    # Check that log was successfully emitted
    tx_receipt = web3.eth.getTransactionReceipt(tx_hash)
    log = smc_handler.events.RegisterNotary().processReceipt(tx_receipt)[0]['args']
    assert log['index_in_notary_pool'] == 0 and log['notary'] == notary.checksum_address
    fast_forward(smc_handler, 1)

    # Add header
    CHUNK_ROOT_1_0 = b'\x10' * 32
    tx_hash = smc_handler.add_header(
        period=1,
        shard_id=0,
        chunk_root=CHUNK_ROOT_1_0,
        private_key=notary.private_key
    )
    mine(web3, 1)
    # Check that log was successfully emitted
    tx_receipt = web3.eth.getTransactionReceipt(tx_hash)
    log = smc_handler.events.AddHeader().processReceipt(tx_receipt)[0]['args']
    assert log['period'] == 1 and log['shard_id'] == 0 and log['chunk_root'] == CHUNK_ROOT_1_0

    # Submit vote
    sample_index = 0
    pool_index = sampling(smc_handler, 0)[sample_index]
    tx_hash = smc_handler.submit_vote(
        period=1,
        shard_id=0,
        chunk_root=CHUNK_ROOT_1_0,
        index=sample_index,
        private_key=NotaryAccount(pool_index).private_key
    )
    mine(web3, 1)
    # Check that log was successfully emitted
    tx_receipt = web3.eth.getTransactionReceipt(tx_hash)
    log = smc_handler.events.SubmitVote().processReceipt(tx_receipt)[0]['args']
    assert log['period'] == 1 and log['shard_id'] == 0 and log['chunk_root'] == CHUNK_ROOT_1_0 \
        and log['notary'] == NotaryAccount(pool_index).checksum_address
    fast_forward(smc_handler, 1)

    # Deregister
    tx_hash = smc_handler.deregister_notary(private_key=notary.private_key)
    mine(web3, 1)
    # Check that log was successfully emitted
    tx_receipt = web3.eth.getTransactionReceipt(tx_hash)
    log = smc_handler.events.DeregisterNotary().processReceipt(tx_receipt)[0]['args']
    assert log['index_in_notary_pool'] == 0 and log['notary'] == notary.checksum_address \
        and log['deregistered_period'] == 2
    # Fast foward to end of lock up
    fast_forward(smc_handler, smc_handler.config['NOTARY_LOCKUP_LENGTH'] + 1)

    # Release
    tx_hash = smc_handler.release_notary(private_key=notary.private_key)
    mine(web3, 1)
    # Check that log was successfully emitted
    tx_receipt = web3.eth.getTransactionReceipt(tx_hash)
    log = smc_handler.events.ReleaseNotary().processReceipt(tx_receipt)[0]['args']
    assert log['index_in_notary_pool'] == 0 and log['notary'] == notary.checksum_address
