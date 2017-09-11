from collections import defaultdict
import copy

from ethereum.config import default_config
from ethereum import utils

sharding_config = copy.deepcopy(default_config)

# sh ng_config['SERENITY_FORK_BLKNUM'] = 0
sharding_config["HOMESTEAD_FORK_BLKNUM"] = 0
sharding_config["ANTI_DOS_FORK_BLKNUM"] = 0
sharding_config["SPURIOUS_DRAGON_FORK_BLKNUM"] = 0
sharding_config["METROPOLIS_FORK_BLKNUM"] = 2**99
sharding_config['SHARD_COUNT'] = 100
# valmgr_addr: should be modified whenever "the v, r, s in valmgr tx" or
# "the content of the contract" change
sharding_config['VALIDATOR_MANAGER_ADDRESS'] = '0x2712b5D174ACc96a3aBE499Ce488b3139533f916'
sharding_config['USED_RECEIPT_STORE_ADDRESS'] = ''   # TODO
sharding_config['SIG_GASLIMIT'] = 40000
sharding_config['COLLATOR_REWARD'] = 0.002 * utils.denoms.ether
sharding_config['SIG_GASLIMIT'] = 40000
sharding_config['PERIOD_LENGTH'] = 5                 # blocks
sharding_config['SHUFFLING_CYCLE'] = 2500            # blocks
sharding_config['DEPOSIT_SIZE'] = 10 ** 20
sharding_config['CONTRACT_CALL_GAS'] = {
    'VALIDATOR_MANAGER': defaultdict(lambda: 200000, {
        'deposit': 170000,
        'withdraw': 110000, # TODO: is it enough?
        'sample': 400000, # should be large enough, due to the uncertain iterations
        'get_shard_head': 80000,
        'add_header': 170000,
        'tx_to_shard': 180000,
        'get_receipts__value': 70000,
        'get_receipts__shard_id': 70000,
        'get_receipts__to': 70000,
        'get_receipts__sender': 70000,
        'get_receipts__data': 70000
    }),
    'USED_RECEIPT_STORE': defaultdict(lambda: 200000, {
        'get_used_receipts': 40000,
        'add_used_receipt': 90000
    })
}