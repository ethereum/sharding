from cytoolz import (
    merge,
)

from contracts.utils.config import (
    get_sharding_config,
)


def get_sharding_testing_config():
    REPLACED_PARAMTERS = {
        'NOTARY_LOCKUP_LENGTH': 120,
    }
    return merge(
        get_sharding_config(),
        REPLACED_PARAMTERS,
    )
