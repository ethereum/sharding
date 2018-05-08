from cytoolz import (
    merge,
)

from sharding.contracts.utils.config import (
    get_sharding_config,
)


def get_sharding_testing_config():
    REPLACED_PARAMETERS = {
        'SHARD_COUNT': 10,
        'PERIOD_LENGTH': 10,
        'COMMITTEE_SIZE': 6,
        'QUORUM_SIZE': 4,
        'NOTARY_LOCKUP_LENGTH': 60,
    }
    return merge(
        get_sharding_config(),
        REPLACED_PARAMETERS,
    )
