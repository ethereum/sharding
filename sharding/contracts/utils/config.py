from typing import (
    Any,
    Dict,
)
from eth_utils import (
    to_wei,
)

from evm.utils import (
    env,
)


def get_sharding_config() -> Dict[str, Any]:
    return {
        # the number of shards
        'SHARD_COUNT': env.get('PYEVM_SHARDING_SHARD_COUNT', type=int, default=100),
        # the number of blocks in one `period`
        'PERIOD_LENGTH': env.get('PYEVM_SHARDING_PERIOD_LENGTH', type=int, default=100),
        # the maximum valid ahead periods from the current period for `get_eligible_proposer`
        'LOOKAHEAD_PERIODS': env.get('PYEVM_SHARDING_LOOKAHEAD_PERIODS', type=int, default=4),
        'COMMITTEE_SIZE': env.get('PYEVM_COMMITTEE_SIZE', type=int, default=135),
        'QUORUM_SIZE': env.get('PYEVM_QUORUM_SIZE', type=int, default=90),
        # the gas limit of one collation
        'COLLATION_GASLIMIT': env.get(
            'PYEVM_SHARDING_COLLATION_GASLIMIT',
            type=int,
            default=10 ** 7,
        ),
        # the gas limit of verifying a signature
        'SIG_GASLIMIT': env.get('PYEVM_SHARDING_SIG_GASLIMIT', type=int, default=40000),
        'NOTARY_DEPOSIT': env.get(
            'NOTARY_DEPOSIT',
            type=int,
            default=to_wei('1000', 'ether'),
        ),
        'NOTARY_LOCKUP_LENGTH': env.get(
            'NOTARY_LOCKUP_LENGTH',
            type=int,
            default=16128,
        ),
        # the reward for creating a collation
        'NOTARY_REWARD': env.get(
            'PYEVM_SHARDING_NOTARY_REWARD',
            type=int,
            default=to_wei('0.001', 'ether'),
        ),
        # default gas_price
        'GAS_PRICE': env.get('PYEVM_SHARDING_GAS_PRICE', type=int, default=1),
        # default gas, just a large enough gas for smc_handler transactions
        'DEFAULT_GAS': env.get('PYEVM_SHARDING_DEFAULT_GAS', type=int, default=510000),
    }
