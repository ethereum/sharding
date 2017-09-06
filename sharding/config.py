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
<<<<<<< HEAD
sharding_config['VALIDATOR_MANAGER_ADDRESS'] = ''  # TODO
sharding_config['USED_RECEIPT_STORE_ADDRESS'] = ''   # TODO
=======
# TODO: Should we just call the sharding.validator_manager.get_valmgr_addr()
#       to determine the valmgr address here for now? Or add a check in
#       test_validator_manager.py to check if
#       `sharding_config['VALIDATOR_MANAGER_ADDRESS']` equals to
#       `utils.checksum_encode(get_valmgr_addr())`?
#       Because currently we modify the contract so frequently.
sharding_config['VALIDATOR_MANAGER_ADDRESS'] = '0x335355Fa67531225ad09De320a7dfD9A9B4831e3'
sharding_config['USED_RECEIPT_STORE_ADDRESS'] = ''    # TODO
>>>>>>> Added get_shard_list function in validator manager contract
sharding_config['SIG_GASLIMIT'] = 40000
sharding_config['COLLATOR_REWARD'] = 0.002 * utils.denoms.ether
sharding_config['SIG_GASLIMIT'] = 40000
sharding_config['PERIOD_LENGTH'] = 5                 # blocks
sharding_config['SHUFFLING_CYCLE'] = 2500            # blocks
sharding_config['DEPOSIT_SIZE'] = 10 ** 20
sharding_config['CONTRACT_CALL_GAS'] = {
    'VALIDATOR_MANAGER': defaultdict(lambda: 200000, {
        'deposit': 160000,
        'withdraw': 100000,
        'sample': 40000,
        'get_shard_head': 40000,
        'add_header': 150000,
        'tx_to_shard': 200000,
        'get_receipts__value': 40000,
        'get_receipts__shard_id': 40000,
        'get_receipts__to': 40000,
        'get_receipts__sender': 40000,
        'get_receipts__data': 40000,
        'get_receipts__tx_startgas': 40000,
        'get_receipts__tx_gasprice': 40000,
    }),
    'USED_RECEIPT_STORE': defaultdict(lambda: 200000, {
        'get_used_receipts': 40000,
        'add_used_receipt': 90000,
    })
}