from eth_utils import (
    event_abi_to_log_topic,
    to_dict,
    to_checksum_address,
    decode_hex,
    big_endian_to_int,
)

from sharding.contracts.utils.smc_utils import (
    get_smc_json,
)


@to_dict
def parse_register_notary_log(log):
    notary = log['topics'][1][-20:]
    data_bytes = decode_hex(log['data'])
    index_in_notary_pool = big_endian_to_int(data_bytes[:32])
    yield 'index_in_notary_pool', index_in_notary_pool
    yield 'notary', to_checksum_address(notary)


@to_dict
def parse_deregister_notary_log(log):
    notary = log['topics'][1][-20:]
    data_bytes = decode_hex(log['data'])
    index_in_notary_pool = big_endian_to_int(data_bytes[:32])
    deregistered_period = big_endian_to_int(data_bytes[32:])
    yield 'index_in_notary_pool', index_in_notary_pool
    yield 'notary', to_checksum_address(notary)
    yield 'deregistered_period', deregistered_period


@to_dict
def parse_release_notary_log(log):
    notary = log['topics'][1][-20:]
    data_bytes = decode_hex(log['data'])
    index_in_notary_pool = big_endian_to_int(data_bytes[:32])
    yield 'index_in_notary_pool', index_in_notary_pool
    yield 'notary', to_checksum_address(notary)


@to_dict
def parse_add_header_log(log):
    shard_id = big_endian_to_int(log['topics'][1])
    data_bytes = decode_hex(log['data'])
    period = big_endian_to_int(data_bytes[:32])
    chunk_root = data_bytes[32:]
    yield 'period', period
    yield 'shard_id', shard_id
    yield 'chunk_root', chunk_root


@to_dict
def parse_submit_vote_log(log):
    shard_id = big_endian_to_int(log['topics'][1])
    data_bytes = decode_hex(log['data'])
    period = big_endian_to_int(data_bytes[:32])
    chunk_root = data_bytes[32:64]
    notary = data_bytes[-20:]
    yield 'period', period
    yield 'shard_id', shard_id
    yield 'chunk_root', chunk_root
    yield 'notary', to_checksum_address(notary)


def get_event_signature_from_abi(event_name):
    for function in get_smc_json()['abi']:
        if function['name'] == event_name and function['type'] == 'event':
            return event_abi_to_log_topic(function)
