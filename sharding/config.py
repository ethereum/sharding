import copy
from ethereum.config import default_config

sharding_config = copy.deepcopy(default_config)
# sharding_config['HOMESTEAD_FORK_BLKNUM'] = 0
# sharding_config['METROPOLIS_FORK_BLKNUM'] = 0
# sharding_config['SERENITY_FORK_BLKNUM'] = 0
# sharding_config['MAX_SHARD_DEPTH'] = 4
# sharding_config['SHARD_CHILD_COUNT'] = 3
# sharding_config['SIGNATURE_COUNT'] = 12
# sharding_config['VALIDATOR_MANAGER_ADDRESS'] = ''  # TODO
# sharding_config['SIG_GASLIMIT'] = 200000
# sharding_config['ROOT_SHARD_SIGNER_REWARD'] = 0.002
# sharding_config['SHARD_REWARD_DECAY_FACTOR'] = 3
# sharding_config['SHUFFLING_CYCLE'] = 2500

sharding_config['HOMESTEAD_FORK_BLKNUM'] = 0
sharding_config['METROPOLIS_FORK_BLKNUM'] = 0
sharding_config['SERENITY_FORK_BLKNUM'] = 0
sharding_config['SHARD_COUNT'] = 100
sharding_config['VALIDATOR_MANAGER_ADDRESS'] = ''  # TODO
sharding_config['USED_RECEIPT_STORE_ADDRESS'] = ''  # TODO
sharding_config['SIG_GASLIMIT'] = 40000
sharding_config['COLLATOR_REWARD'] = 0.002
sharding_config['SIG_GASLIMIT'] = 40000
sharding_config['PERIOD_LENGTH'] = 5 # blocks
sharding_config['SHUFFLING_CYCLE'] = 2500 # blocks
