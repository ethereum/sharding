from eth_utils import (
    event_abi_to_log_topic,
    to_dict,
    encode_hex,
    decode_hex,
    big_endian_to_int,
)

from sharding.contracts.utils.smc_utils import (
    get_smc_json,
)


@to_dict
def parse_add_header_log(log):
    # `shard_id` is the first indexed entry,hence the second entry in topics
    shard_id = big_endian_to_int(log['topics'][1])
    data_bytes = decode_hex(log['data'])
    period = big_endian_to_int(data_bytes[:32])
    chunk_root = data_bytes[32:]
    yield 'period', period
    yield 'shard_id', shard_id
    yield 'chunk_root', chunk_root


def get_event_signature_from_abi(event_name):
    for function in get_smc_json()['abi']:
        if function['name'] == event_name and function['type'] == 'event':
            return encode_hex(event_abi_to_log_topic(function))
