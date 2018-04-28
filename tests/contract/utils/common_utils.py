from sharding.handler.utils.web3_utils import (
    mine,
)
from tests.contract.utils.notary_account import (
    TestingNotaryAccount,
)


def update_notary_sample_size(smc_handler):
    smc_handler._send_transaction(
        'update_notary_sample_size',
        [],
        private_key=TestingNotaryAccount(0).private_key,
        gas=smc_handler.config['DEFAULT_GAS'],
    )
    mine(smc_handler.web3, 1)


def batch_register(smc_handler, start, end):
    assert start <= end
    for i in range(start, end + 1):
        notary = TestingNotaryAccount(i)
        smc_handler.register_notary(private_key=notary.private_key)
    mine(smc_handler.web3, 1)


def fast_forward(smc_handler, num_of_periods):
    assert num_of_periods > 0
    period_length = smc_handler.config['PERIOD_LENGTH']
    block_number = smc_handler.web3.eth.blockNumber
    current_period = block_number // period_length
    blocks_to_the_period = (current_period + num_of_periods) * period_length \
        - block_number
    mine(smc_handler.web3, blocks_to_the_period)
