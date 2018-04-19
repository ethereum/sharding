from cytoolz import (
    merge,
)

from contracts.utils.config import (
    get_sharding_config,
)


def get_sharding_testing_config():
    REPLACED_PARAMETERS = {
        'PERIOD_LENGTH': 5,
        'COMMITTEE_SIZE': 6,
        'QUORUM_SIZE': 4,
        'NOTARY_LOCKUP_LENGTH': 120,
    }
    return merge(
        get_sharding_config(),
        REPLACED_PARAMETERS,
    )
