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
        'SHARD_COUNT': env.get('SHARDING_SHARD_COUNT', type=int, default=100),
        'PERIOD_LENGTH': env.get('SHARDING_PERIOD_LENGTH', type=int, default=100),
        'LOOKAHEAD_LENGTH': env.get('SHARDING_LOOKAHEAD_LENGTH', type=int, default=4),
        'COMMITTEE_SIZE': env.get('SHARDING_COMMITTEE_SIZE', type=int, default=135),
        'QUORUM_SIZE': env.get('SHARDING_QUORUM_SIZE', type=int, default=90),
        'NOTARY_DEPOSIT': env.get(
            'SHARDING_NOTARY_DEPOSIT',
            type=int,
            default=to_wei('1000', 'ether'),
        ),
        'NOTARY_LOCKUP_LENGTH': env.get(
            'SHARDING_NOTARY_LOCKUP_LENGTH',
            type=int,
            default=16128,
        ),
        'NOTARY_REWARD': env.get(
            'SHARDING_NOTARY_REWARD',
            type=int,
            default=to_wei('0.001', 'ether'),
        ),
        'GAS_PRICE': env.get('SHARDING_GAS_PRICE', type=int, default=1),
    }
