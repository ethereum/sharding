import copy
from ethereum.config import default_config
from ethereum import utils

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
# valmgr_addr: should be modified whenever "the v, r, s in valmgr tx" or
# "the content of the contract" change
# TODO: Should we just call the sharding.validator_manager.get_valmgr_addr()
#       to determine the valmgr address here for now? Or add a check in
#       test_validator_manager.py to check if
#       `sharding_config['VALIDATOR_MANAGER_ADDRESS']` equals to
#       `utils.checksum_encode(get_valmgr_addr())`?
#       Because currently we modify the contract so frequently.
sharding_config['VALIDATOR_MANAGER_ADDRESS'] = '0x8dcD67edcEbb9C169bDb16F7c9fAc19E34d633D0'
sharding_config['USED_RECEIPT_STORE_ADDRESS'] = ''   # TODO
sharding_config['SIG_GASLIMIT'] = 40000
sharding_config['COLLATOR_REWARD'] = 0.002 * utils.denoms.ether
sharding_config['SIG_GASLIMIT'] = 40000
sharding_config['PERIOD_LENGTH'] = 5 # blocks
sharding_config['SHUFFLING_CYCLE'] = 2500 # blocks
