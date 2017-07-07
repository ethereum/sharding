import copy
from ethereum.config import default_config

sharding_config = copy.deepcopy(default_config)
sharding_config['HOMESTEAD_FORK_BLKNUM'] = 0
sharding_config['METROPOLIS_FORK_BLKNUM'] = 0
sharding_config['SERENITY_FORK_BLKNUM'] = 0
sharding_config['MAX_SHARD_DEPTH'] = 4
sharding_config['SHARD_CHILD_COUNT'] = 3
sharding_config['SIGNATURE_COUNT'] = 12
sharding_config['VALIDATOR_MANAGER_ADDRESS'] = ''  # TODO
sharding_config['SIG_GASLIMIT'] = 200000
sharding_config['SHARD_POW_DIFFICULTY'] = 2**36
sharding_config['ROOT_SHARD_COLLATOR_REWARD'] = 0.1
sharding_config['ROOT_SHARD_SIGNER_REWARD'] = 0.002
sharding_config['SHARD_REWARD_DECAY_FACTOR'] = 3
