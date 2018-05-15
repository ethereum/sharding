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
from sharding.handler.utils.headers import (
    CollationHeader,
)


@to_dict
def parse_collation_added_log(log):
    # `shard_id` is the first indexed entry,hence the second entry in topics
    shard_id_bytes32 = log['topics'][1]
    data_bytes = decode_hex(log['data'])
    header_bytes = shard_id_bytes32 + data_bytes[:-64]
    is_new_head = bool(big_endian_to_int(data_bytes[-64:-32]))
    score = big_endian_to_int(data_bytes[-32:])
    collation_header = CollationHeader.from_bytes(header_bytes)
    yield 'header', collation_header
    yield 'is_new_head', is_new_head
    yield 'score', score


def get_event_signature_from_abi(event_name):
    for function in get_smc_json()['abi']:
        if function['name'] == event_name and function['type'] == 'event':
            return encode_hex(event_abi_to_log_topic(function))
