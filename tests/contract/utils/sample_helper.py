from eth_utils import (
    to_list,
    keccak,
    big_endian_to_int,
)

from evm.utils.numeric import (
    int_to_bytes32,
)


@to_list
def get_notary_pool_list(smc_handler):
    """Get the full list of notaries that's currently in notary pool.
    """
    pool_len = smc_handler.notary_pool_len()
    for i in range(pool_len):
        yield smc_handler.notary_pool(i)


@to_list
def get_committee_list(smc_handler, shard_id):
    """Get committee list in specified shard in current period.
    Index starts from zero to COMMITTEE_SIZE-1
    """
    bytes32_shard_id = int_to_bytes32(shard_id)
    web3 = smc_handler.web3
    current_period = web3.eth.blockNumber // smc_handler.config['PERIOD_LENGTH']

    if smc_handler.notary_sample_size_updated_period() < current_period:
        sample_size = smc_handler.next_period_notary_sample_size()
    elif smc_handler.notary_sample_size_updated_period() == current_period:
        sample_size = smc_handler.current_period_notary_sample_size()
    else:
        raise Exception("notary_sample_size_updated_period is larger than current period")

    entropy_block_number = current_period * smc_handler.config['PERIOD_LENGTH'] - 1
    entropy_block_hash = web3.eth.getBlock(entropy_block_number)['hash']
    for i in range(smc_handler.config['COMMITTEE_SIZE']):
        pool_index = big_endian_to_int(
            keccak(
                entropy_block_hash + bytes32_shard_id + int_to_bytes32(i)
            )
        ) % sample_size
        yield smc_handler.notary_pool(pool_index)


@to_list
def get_sample_result(smc_handler, notary_index):
    """Get sampling result for the specified notary. Pass in notary's index in notary pool.
    Returns a list of tuple(shard_id, index) indicating on which shard is the notary sampled
    and by which sampling index.
    """
    web3 = smc_handler.web3
    current_period = web3.eth.blockNumber // smc_handler.config['PERIOD_LENGTH']

    if smc_handler.notary_sample_size_updated_period() < current_period:
        sample_size = smc_handler.next_period_notary_sample_size()
    elif smc_handler.notary_sample_size_updated_period() == current_period:
        sample_size = smc_handler.current_period_notary_sample_size()
    else:
        raise Exception("notary_sample_size_updated_period is larger than current period")

    for shard_id in range(smc_handler.config['SHARD_COUNT']):
        bytes32_shard_id = int_to_bytes32(shard_id)
        entropy_block_number = current_period * smc_handler.config['PERIOD_LENGTH'] - 1
        entropy_block_hash = web3.eth.getBlock(entropy_block_number)['hash']
        for index in range(smc_handler.config['COMMITTEE_SIZE']):
            pool_index = big_endian_to_int(
                keccak(
                    entropy_block_hash + bytes32_shard_id + int_to_bytes32(index)
                )
            ) % sample_size
            if pool_index == notary_index:
                yield (shard_id, index)
