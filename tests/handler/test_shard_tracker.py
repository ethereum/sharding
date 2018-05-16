import logging

import pytest

from sharding.handler.utils.shard_tracker_utils import (
    parse_register_notary_log,
    parse_deregister_notary_log,
    parse_add_header_log,
    parse_submit_vote_log,
)

from tests.handler.fixtures import (  # noqa: F401
    smc_handler,
)


logger = logging.getLogger('evm.chain.sharding.mainchain_handler.ShardTracker')


@pytest.mark.parametrize(
    'raw_log, index_in_notary_pool, notary',
    (
        (
            {'type': 'mined', 'logIndex': 0, 'transactionIndex': 0, 'transactionHash': b'\xda\xb8:\xe5\x86\xe9Q\xf2\x9c\xc6<g\x9bl\x84\x85\xf4\x1dh\xce\x8d\xe6\xc0D\xa0*E\xd8m\xd4\x01\xcf', 'blockHash': b'\x13\xa97d\r\x90t\xe5;\x84\xf9\xe0\xb8\xf2c\x1c}\x88\xbf\x84DN\xa0\x16Q\xd9|\xa1\x00\x91\xc0\xbd', 'blockNumber': 25, 'address': '0xf4F1600B0a65995833854738764b50A4DA8d6BE1', 'data': '0x0000000000000000000000000000000000000000000000000000000000000000', 'topics': [b'B\xccp\x0f[x\xa7Le \xecSA\xd7\xc4\x9e\xea\xa8\xf8\x90\x15\xe7\x14\xb4\xd7 |\x94|-\x19\xec', b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00~_ER\t\x1ai\x12]]\xfc\xb7\xb8\xc2e\x90)9[\xdf']},  # noqa: E501
            0,
            '0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf',
        ),
        (
            {'type': 'mined', 'logIndex': 0, 'transactionIndex': 0, 'transactionHash': b'\x16\xc2\x0b\xadZ|\x92l@@\xb1\x15\x93nh\xd6]p\x16\xae\xd5\xe7\x9crKl\x8c\xcf\x06\x9a\xd4\x05', 'blockHash': b'\x94\\\xce\x19\x01:j\xbb\xf8\xba\x19\xcfv\xc3z3}^\xb6>\xa0\x0e\xf74\xe8A\t\x12p\x9a\xf6V', 'blockNumber': 30, 'address': '0xf4F1600B0a65995833854738764b50A4DA8d6BE1', 'data': '0x0000000000000000000000000000000000000000000000000000000000000003', 'topics': [b'B\xccp\x0f[x\xa7Le \xecSA\xd7\xc4\x9e\xea\xa8\xf8\x90\x15\xe7\x14\xb4\xd7 |\x94|-\x19\xec', b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x1e\xffG\xbc:\x10\xa4]K#\x0b]\x10\xe3wQ\xfej\xa7\x18']},  # noqa: E501
            3,
            '0x1efF47bc3a10a45D4B230B5d10E37751FE6AA718',
        ),
    )
)
def test_parse_register_notary_log(raw_log, index_in_notary_pool, notary):
    log = parse_register_notary_log(raw_log)
    assert log['index_in_notary_pool'] == index_in_notary_pool
    assert log['notary'] == notary


@pytest.mark.parametrize(
    'raw_log, index_in_notary_pool, notary, deregistered_period',
    (
        (
            {'type': 'mined', 'logIndex': 0, 'transactionIndex': 0, 'transactionHash': b'\xda\xb8:\xe5\x86\xe9Q\xf2\x9c\xc6<g\x9bl\x84\x85\xf4\x1dh\xce\x8d\xe6\xc0D\xa0*E\xd8m\xd4\x01\xcf', 'blockHash': b'\x13\xa97d\r\x90t\xe5;\x84\xf9\xe0\xb8\xf2c\x1c}\x88\xbf\x84DN\xa0\x16Q\xd9|\xa1\x00\x91\xc0\xbd', 'blockNumber': 25, 'address': '0xf4F1600B0a65995833854738764b50A4DA8d6BE1', 'data': '0x0000000000000000000000000000000000000000000000000000000000000005000000000000000000000000000000000000000000000000000000000000000a', 'topics': [b'B\xccp\x0f[x\xa7Le \xecSA\xd7\xc4\x9e\xea\xa8\xf8\x90\x15\xe7\x14\xb4\xd7 |\x94|-\x19\xec', b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00~_ER\t\x1ai\x12]]\xfc\xb7\xb8\xc2e\x90)9[\xdf']},  # noqa: E501
            5,
            '0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf',
            10,
        ),
        (
            {'type': 'mined', 'logIndex': 0, 'transactionIndex': 0, 'transactionHash': b'\x16\xc2\x0b\xadZ|\x92l@@\xb1\x15\x93nh\xd6]p\x16\xae\xd5\xe7\x9crKl\x8c\xcf\x06\x9a\xd4\x05', 'blockHash': b'\x94\\\xce\x19\x01:j\xbb\xf8\xba\x19\xcfv\xc3z3}^\xb6>\xa0\x0e\xf74\xe8A\t\x12p\x9a\xf6V', 'blockNumber': 30, 'address': '0xf4F1600B0a65995833854738764b50A4DA8d6BE1', 'data': '0x00000000000000000000000000000000000000000000000000000000000000100000000000000000000000000000000000000000000000000000000000000005', 'topics': [b'B\xccp\x0f[x\xa7Le \xecSA\xd7\xc4\x9e\xea\xa8\xf8\x90\x15\xe7\x14\xb4\xd7 |\x94|-\x19\xec', b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x1e\xffG\xbc:\x10\xa4]K#\x0b]\x10\xe3wQ\xfej\xa7\x18']},  # noqa: E501
            16,
            '0x1efF47bc3a10a45D4B230B5d10E37751FE6AA718',
            5,
        ),
    )
)
def test_parse_deregister_notary_log(raw_log, index_in_notary_pool, notary, deregistered_period):
    log = parse_deregister_notary_log(raw_log)
    assert log['index_in_notary_pool'] == index_in_notary_pool
    assert log['notary'] == notary
    assert log['deregistered_period'] == deregistered_period


@pytest.mark.parametrize(
    'raw_log, period, shard_id, chunk_root',
    (
        (
            {'type': 'mined', 'logIndex': 0, 'transactionIndex': 0, 'transactionHash': b'\xda\xb8:\xe5\x86\xe9Q\xf2\x9c\xc6<g\x9bl\x84\x85\xf4\x1dh\xce\x8d\xe6\xc0D\xa0*E\xd8m\xd4\x01\xcf', 'blockHash': b'\x13\xa97d\r\x90t\xe5;\x84\xf9\xe0\xb8\xf2c\x1c}\x88\xbf\x84DN\xa0\x16Q\xd9|\xa1\x00\x91\xc0\xbd', 'blockNumber': 25, 'address': '0xf4F1600B0a65995833854738764b50A4DA8d6BE1', 'data': '0x00000000000000000000000000000000000000000000000000000000000000011010101010101010101010101010101010101010101010101010101010101010', 'topics': [b'$\xa5\x146ipE\xb9:y\xa2\xbd\xa9\x00\xb0PU\xf1\xe1\xe9\x1b\x02\x1bL/\xb6\xf6|\xbb\x0b.\x95', b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00']},  # noqa: E501
            1,
            0,
            b'\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10',  # noqa: E501
        ),
        (
            {'type': 'mined', 'logIndex': 0, 'transactionIndex': 0, 'transactionHash': b'\x16\xc2\x0b\xadZ|\x92l@@\xb1\x15\x93nh\xd6]p\x16\xae\xd5\xe7\x9crKl\x8c\xcf\x06\x9a\xd4\x05', 'blockHash': b'\x94\\\xce\x19\x01:j\xbb\xf8\xba\x19\xcfv\xc3z3}^\xb6>\xa0\x0e\xf74\xe8A\t\x12p\x9a\xf6V', 'blockNumber': 30, 'address': '0xf4F1600B0a65995833854738764b50A4DA8d6BE1', 'data': '0x00000000000000000000000000000000000000000000000000000000000000077373737373737373737373737373737373737373737373737373737373737373', 'topics': [b'$\xa5\x146ipE\xb9:y\xa2\xbd\xa9\x00\xb0PU\xf1\xe1\xe9\x1b\x02\x1bL/\xb6\xf6|\xbb\x0b.\x95', b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x03']},  # noqa: E501
            7,
            3,
            b'ssssssssssssssssssssssssssssssss',
        ),
    )
)
def test_parse_add_header_log(raw_log, period, shard_id, chunk_root):
    log = parse_add_header_log(raw_log)
    assert log['period'] == period
    assert log['shard_id'] == shard_id
    assert log['chunk_root'] == chunk_root


@pytest.mark.parametrize(
    'raw_log, period, shard_id, chunk_root, notary',
    (
        (
            {'type': 'mined', 'logIndex': 0, 'transactionIndex': 0, 'transactionHash': b'\xda\xb8:\xe5\x86\xe9Q\xf2\x9c\xc6<g\x9bl\x84\x85\xf4\x1dh\xce\x8d\xe6\xc0D\xa0*E\xd8m\xd4\x01\xcf', 'blockHash': b'\x13\xa97d\r\x90t\xe5;\x84\xf9\xe0\xb8\xf2c\x1c}\x88\xbf\x84DN\xa0\x16Q\xd9|\xa1\x00\x91\xc0\xbd', 'blockNumber': 25, 'address': '0xf4F1600B0a65995833854738764b50A4DA8d6BE1', 'data': '0x000000000000000000000000000000000000000000000000000000000000001010011001100110011001100110011001100110011001100110011001100110010000000000000000000000001eff47bc3a10a45d4b230b5d10e37751fe6aa718', 'topics': [b'$\xa5\x146ipE\xb9:y\xa2\xbd\xa9\x00\xb0PU\xf1\xe1\xe9\x1b\x02\x1bL/\xb6\xf6|\xbb\x0b.\x95', b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01']},  # noqa: E501
            16,
            1,
            b'\x10\x01\x10\x01\x10\x01\x10\x01\x10\x01\x10\x01\x10\x01\x10\x01\x10\x01\x10\x01\x10\x01\x10\x01\x10\x01\x10\x01\x10\x01\x10\x01',  # noqa: E501
            '0x1efF47bc3a10a45D4B230B5d10E37751FE6AA718',
        ),
        (
            {'type': 'mined', 'logIndex': 0, 'transactionIndex': 0, 'transactionHash': b'\x16\xc2\x0b\xadZ|\x92l@@\xb1\x15\x93nh\xd6]p\x16\xae\xd5\xe7\x9crKl\x8c\xcf\x06\x9a\xd4\x05', 'blockHash': b'\x94\\\xce\x19\x01:j\xbb\xf8\xba\x19\xcfv\xc3z3}^\xb6>\xa0\x0e\xf74\xe8A\t\x12p\x9a\xf6V', 'blockNumber': 30, 'address': '0xf4F1600B0a65995833854738764b50A4DA8d6BE1', 'data': '0x000000000000000000000000000000000000000000000000000000000000002121632163216321632163216321632163216321632163216321632163216321630000000000000000000000007e5f4552091a69125d5dfcb7b8c2659029395bdf', 'topics': [b'$\xa5\x146ipE\xb9:y\xa2\xbd\xa9\x00\xb0PU\xf1\xe1\xe9\x1b\x02\x1bL/\xb6\xf6|\xbb\x0b.\x95', b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x63']},  # noqa: E501
            33,
            99,
            b'!c!c!c!c!c!c!c!c!c!c!c!c!c!c!c!c',
            '0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf',
        ),
    )
)
def test_parse_submit_vote_log(raw_log, period, shard_id, chunk_root, notary):
    log = parse_submit_vote_log(raw_log)
    assert log['period'] == period
    assert log['shard_id'] == shard_id
    assert log['chunk_root'] == chunk_root
    assert log['notary'] == notary
