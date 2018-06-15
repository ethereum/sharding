import pkg_resources

from sharding.contracts.utils.smc_utils import (  # noqa: F401
    get_smc_source_code,
    get_smc_json,
)

from sharding.handler.log_handler import (  # noqa: F401
    LogHandler,
)
from sharding.handler.shard_tracker import (  # noqa: F401
    ShardTracker,
)
from sharding.handler.smc_handler import (  # noqa: F401
    SMC,
)


__version__ = pkg_resources.get_distribution("sharding").version
