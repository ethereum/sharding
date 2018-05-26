import logging

import pytest

from sharding.handler.exceptions import (
    LogParsingError,
)
from sharding.handler.utils.log_parser import (
    LogParser,
)
from sharding.handler.log_handler import (  # noqa: F401
    LogHandler,
)
from sharding.handler.shard_tracker import (  # noqa: F401
    ShardTracker,
)
from sharding.handler.utils.web3_utils import (
    mine,
)

from tests.handler.fixtures import (  # noqa: F401
    smc_handler,
)
from tests.handler.utils.config import (
    get_sharding_testing_config,
)
from tests.contract.utils.common_utils import (
    batch_register,
    fast_forward,
)
from tests.contract.utils.notary_account import (
    NotaryAccount,
)
from tests.contract.utils.sample_helper import (
    sampling,
)


logger = logging.getLogger('sharding.handler.ShardTracker')


@pytest.mark.parametrize(
    'raw_log, event_name, attr_tuples',
    (
        (
            {'type': 'mined', 'logIndex': 0, 'transactionIndex': 0, 'transactionHash': b'\xda\xb8:\xe5\x86\xe9Q\xf2\x9c\xc6<g\x9bl\x84\x85\xf4\x1dh\xce\x8d\xe6\xc0D\xa0*E\xd8m\xd4\x01\xcf', 'blockHash': b'\x13\xa97d\r\x90t\xe5;\x84\xf9\xe0\xb8\xf2c\x1c}\x88\xbf\x84DN\xa0\x16Q\xd9|\xa1\x00\x91\xc0\xbd', 'blockNumber': 25, 'address': '0xf4F1600B0a65995833854738764b50A4DA8d6BE1', 'data': '0x0000000000000000000000000000000000000000000000000000000000000000', 'topics': [b'B\xccp\x0f[x\xa7Le \xecSA\xd7\xc4\x9e\xea\xa8\xf8\x90\x15\xe7\x14\xb4\xd7 |\x94|-\x19\xec', b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00~_ER\t\x1ai\x12]]\xfc\xb7\xb8\xc2e\x90)9[\xdf']},  # noqa: E501
            'RegisterNotary',
            [
                ('index_in_notary_pool', 0),
                ('notary', '0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf'),
            ]
        ),
        (
            {'type': 'mined', 'logIndex': 0, 'transactionIndex': 0, 'transactionHash': b'\x16\xc2\x0b\xadZ|\x92l@@\xb1\x15\x93nh\xd6]p\x16\xae\xd5\xe7\x9crKl\x8c\xcf\x06\x9a\xd4\x05', 'blockHash': b'\x94\\\xce\x19\x01:j\xbb\xf8\xba\x19\xcfv\xc3z3}^\xb6>\xa0\x0e\xf74\xe8A\t\x12p\x9a\xf6V', 'blockNumber': 30, 'address': '0xf4F1600B0a65995833854738764b50A4DA8d6BE1', 'data': '0x0000000000000000000000000000000000000000000000000000000000000003', 'topics': [b'B\xccp\x0f[x\xa7Le \xecSA\xd7\xc4\x9e\xea\xa8\xf8\x90\x15\xe7\x14\xb4\xd7 |\x94|-\x19\xec', b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x1e\xffG\xbc:\x10\xa4]K#\x0b]\x10\xe3wQ\xfej\xa7\x18']},  # noqa: E501
            'RegisterNotary',
            [
                ('index_in_notary_pool', 3),
                ('notary', '0x1efF47bc3a10a45D4B230B5d10E37751FE6AA718'),
            ]
        ),
        (
            {'type': 'mined', 'logIndex': 0, 'transactionIndex': 0, 'transactionHash': b'\xda\xb8:\xe5\x86\xe9Q\xf2\x9c\xc6<g\x9bl\x84\x85\xf4\x1dh\xce\x8d\xe6\xc0D\xa0*E\xd8m\xd4\x01\xcf', 'blockHash': b'\x13\xa97d\r\x90t\xe5;\x84\xf9\xe0\xb8\xf2c\x1c}\x88\xbf\x84DN\xa0\x16Q\xd9|\xa1\x00\x91\xc0\xbd', 'blockNumber': 25, 'address': '0xf4F1600B0a65995833854738764b50A4DA8d6BE1', 'data': '0x0000000000000000000000000000000000000000000000000000000000000005000000000000000000000000000000000000000000000000000000000000000a', 'topics': [b'B\xccp\x0f[x\xa7Le \xecSA\xd7\xc4\x9e\xea\xa8\xf8\x90\x15\xe7\x14\xb4\xd7 |\x94|-\x19\xec', b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00~_ER\t\x1ai\x12]]\xfc\xb7\xb8\xc2e\x90)9[\xdf']},  # noqa: E501
            'DeregisterNotary',
            [
                ('index_in_notary_pool', 5),
                ('notary', '0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf'),
                ('deregistered_period', 10),
            ]
        ),
        (
            {'type': 'mined', 'logIndex': 0, 'transactionIndex': 0, 'transactionHash': b'\x16\xc2\x0b\xadZ|\x92l@@\xb1\x15\x93nh\xd6]p\x16\xae\xd5\xe7\x9crKl\x8c\xcf\x06\x9a\xd4\x05', 'blockHash': b'\x94\\\xce\x19\x01:j\xbb\xf8\xba\x19\xcfv\xc3z3}^\xb6>\xa0\x0e\xf74\xe8A\t\x12p\x9a\xf6V', 'blockNumber': 30, 'address': '0xf4F1600B0a65995833854738764b50A4DA8d6BE1', 'data': '0x00000000000000000000000000000000000000000000000000000000000000100000000000000000000000000000000000000000000000000000000000000005', 'topics': [b'B\xccp\x0f[x\xa7Le \xecSA\xd7\xc4\x9e\xea\xa8\xf8\x90\x15\xe7\x14\xb4\xd7 |\x94|-\x19\xec', b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x1e\xffG\xbc:\x10\xa4]K#\x0b]\x10\xe3wQ\xfej\xa7\x18']},  # noqa: E501
            'DeregisterNotary',
            [
                ('index_in_notary_pool', 16),
                ('notary', '0x1efF47bc3a10a45D4B230B5d10E37751FE6AA718'),
                ('deregistered_period', 5),
            ]
        ),
        (
            {'type': 'mined', 'logIndex': 0, 'transactionIndex': 0, 'transactionHash': b'\xda\xb8:\xe5\x86\xe9Q\xf2\x9c\xc6<g\x9bl\x84\x85\xf4\x1dh\xce\x8d\xe6\xc0D\xa0*E\xd8m\xd4\x01\xcf', 'blockHash': b'\x13\xa97d\r\x90t\xe5;\x84\xf9\xe0\xb8\xf2c\x1c}\x88\xbf\x84DN\xa0\x16Q\xd9|\xa1\x00\x91\xc0\xbd', 'blockNumber': 25, 'address': '0xf4F1600B0a65995833854738764b50A4DA8d6BE1', 'data': '0x00000000000000000000000000000000000000000000000000000000000000011010101010101010101010101010101010101010101010101010101010101010', 'topics': [b'$\xa5\x146ipE\xb9:y\xa2\xbd\xa9\x00\xb0PU\xf1\xe1\xe9\x1b\x02\x1bL/\xb6\xf6|\xbb\x0b.\x95', b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00']},  # noqa: E501
            'AddHeader',
            [
                ('period', 1),
                ('shard_id', 0),
                ('chunk_root', b'\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10\x10'),  # noqa: E501
            ]
        ),
        (
            {'type': 'mined', 'logIndex': 0, 'transactionIndex': 0, 'transactionHash': b'\x16\xc2\x0b\xadZ|\x92l@@\xb1\x15\x93nh\xd6]p\x16\xae\xd5\xe7\x9crKl\x8c\xcf\x06\x9a\xd4\x05', 'blockHash': b'\x94\\\xce\x19\x01:j\xbb\xf8\xba\x19\xcfv\xc3z3}^\xb6>\xa0\x0e\xf74\xe8A\t\x12p\x9a\xf6V', 'blockNumber': 30, 'address': '0xf4F1600B0a65995833854738764b50A4DA8d6BE1', 'data': '0x00000000000000000000000000000000000000000000000000000000000000077373737373737373737373737373737373737373737373737373737373737373', 'topics': [b'$\xa5\x146ipE\xb9:y\xa2\xbd\xa9\x00\xb0PU\xf1\xe1\xe9\x1b\x02\x1bL/\xb6\xf6|\xbb\x0b.\x95', b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x03']},  # noqa: E501
            'AddHeader',
            [
                ('period', 7),
                ('shard_id', 3),
                ('chunk_root', b'ssssssssssssssssssssssssssssssss'),
            ]
        ),
        (
            {'type': 'mined', 'logIndex': 0, 'transactionIndex': 0, 'transactionHash': b'\xda\xb8:\xe5\x86\xe9Q\xf2\x9c\xc6<g\x9bl\x84\x85\xf4\x1dh\xce\x8d\xe6\xc0D\xa0*E\xd8m\xd4\x01\xcf', 'blockHash': b'\x13\xa97d\r\x90t\xe5;\x84\xf9\xe0\xb8\xf2c\x1c}\x88\xbf\x84DN\xa0\x16Q\xd9|\xa1\x00\x91\xc0\xbd', 'blockNumber': 25, 'address': '0xf4F1600B0a65995833854738764b50A4DA8d6BE1', 'data': '0x000000000000000000000000000000000000000000000000000000000000001010011001100110011001100110011001100110011001100110011001100110010000000000000000000000001eff47bc3a10a45d4b230b5d10e37751fe6aa718', 'topics': [b'$\xa5\x146ipE\xb9:y\xa2\xbd\xa9\x00\xb0PU\xf1\xe1\xe9\x1b\x02\x1bL/\xb6\xf6|\xbb\x0b.\x95', b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01']},  # noqa: E501
            'SubmitVote',
            [
                ('period', 16),
                ('shard_id', 1),
                ('chunk_root', b'\x10\x01\x10\x01\x10\x01\x10\x01\x10\x01\x10\x01\x10\x01\x10\x01\x10\x01\x10\x01\x10\x01\x10\x01\x10\x01\x10\x01\x10\x01\x10\x01'),  # noqa: E501
                ('notary', '0x1efF47bc3a10a45D4B230B5d10E37751FE6AA718'),
            ]
        ),
        (
            {'type': 'mined', 'logIndex': 0, 'transactionIndex': 0, 'transactionHash': b'\x16\xc2\x0b\xadZ|\x92l@@\xb1\x15\x93nh\xd6]p\x16\xae\xd5\xe7\x9crKl\x8c\xcf\x06\x9a\xd4\x05', 'blockHash': b'\x94\\\xce\x19\x01:j\xbb\xf8\xba\x19\xcfv\xc3z3}^\xb6>\xa0\x0e\xf74\xe8A\t\x12p\x9a\xf6V', 'blockNumber': 30, 'address': '0xf4F1600B0a65995833854738764b50A4DA8d6BE1', 'data': '0x000000000000000000000000000000000000000000000000000000000000002121632163216321632163216321632163216321632163216321632163216321630000000000000000000000007e5f4552091a69125d5dfcb7b8c2659029395bdf', 'topics': [b'$\xa5\x146ipE\xb9:y\xa2\xbd\xa9\x00\xb0PU\xf1\xe1\xe9\x1b\x02\x1bL/\xb6\xf6|\xbb\x0b.\x95', b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x63']},  # noqa: E501
            'SubmitVote',
            [
                ('period', 33),
                ('shard_id', 99),
                ('chunk_root', b'!c!c!c!c!c!c!c!c!c!c!c!c!c!c!c!c'),
                ('notary', '0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf'),
            ]
        ),
    )
)
def test_normal_log_parser(raw_log, event_name, attr_tuples):
    parsed_log = LogParser(event_name=event_name, log=raw_log)
    for attr in attr_tuples:
        assert getattr(parsed_log, attr[0]) == attr[1]


@pytest.mark.parametrize(
    'raw_log, event_name',
    (
        (
            # Wrong event name
            {'type': 'mined', 'logIndex': 0, 'transactionIndex': 0, 'transactionHash': b'\xda\xb8:\xe5\x86\xe9Q\xf2\x9c\xc6<g\x9bl\x84\x85\xf4\x1dh\xce\x8d\xe6\xc0D\xa0*E\xd8m\xd4\x01\xcf', 'blockHash': b'\x13\xa97d\r\x90t\xe5;\x84\xf9\xe0\xb8\xf2c\x1c}\x88\xbf\x84DN\xa0\x16Q\xd9|\xa1\x00\x91\xc0\xbd', 'blockNumber': 25, 'address': '0xf4F1600B0a65995833854738764b50A4DA8d6BE1', 'data': '0x0000000000000000000000000000000000000000000000000000000000000005000000000000000000000000000000000000000000000000000000000000000a', 'topics': [b'B\xccp\x0f[x\xa7Le \xecSA\xd7\xc4\x9e\xea\xa8\xf8\x90\x15\xe7\x14\xb4\xd7 |\x94|-\x19\xec', b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00~_ER\t\x1ai\x12]]\xfc\xb7\xb8\xc2e\x90)9[\xdf']},  # noqa: E501
            'WrongEventName',
        ),
        (
            # Too many topics in log
            {'type': 'mined', 'logIndex': 0, 'transactionIndex': 0, 'transactionHash': b'\xda\xb8:\xe5\x86\xe9Q\xf2\x9c\xc6<g\x9bl\x84\x85\xf4\x1dh\xce\x8d\xe6\xc0D\xa0*E\xd8m\xd4\x01\xcf', 'blockHash': b'\x13\xa97d\r\x90t\xe5;\x84\xf9\xe0\xb8\xf2c\x1c}\x88\xbf\x84DN\xa0\x16Q\xd9|\xa1\x00\x91\xc0\xbd', 'blockNumber': 25, 'address': '0xf4F1600B0a65995833854738764b50A4DA8d6BE1', 'data': '0x0000000000000000000000000000000000000000000000000000000000000000', 'topics': [b'B\xccp\x0f[x\xa7Le \xecSA\xd7\xc4\x9e\xea\xa8\xf8\x90\x15\xe7\x14\xb4\xd7 |\x94|-\x19\xec', b'$\xa5\x146ipE\xb9:y\xa2\xbd\xa9\x00\xb0PU\xf1\xe1\xe9\x1b\x02\x1bL/\xb6\xf6|\xbb\x0b.\x95', b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00~_ER\t\x1ai\x12]]\xfc\xb7\xb8\xc2e\x90)9[\xdf']},  # noqa: E501
            'RegisterNotary',
        ),
        (
            # Too few topics in log
            {'type': 'mined', 'logIndex': 0, 'transactionIndex': 0, 'transactionHash': b'\xda\xb8:\xe5\x86\xe9Q\xf2\x9c\xc6<g\x9bl\x84\x85\xf4\x1dh\xce\x8d\xe6\xc0D\xa0*E\xd8m\xd4\x01\xcf', 'blockHash': b'\x13\xa97d\r\x90t\xe5;\x84\xf9\xe0\xb8\xf2c\x1c}\x88\xbf\x84DN\xa0\x16Q\xd9|\xa1\x00\x91\xc0\xbd', 'blockNumber': 25, 'address': '0xf4F1600B0a65995833854738764b50A4DA8d6BE1', 'data': '0x0000000000000000000000000000000000000000000000000000000000000000', 'topics': [b'B\xccp\x0f[x\xa7Le \xecSA\xd7\xc4\x9e\xea\xa8\xf8\x90\x15\xe7\x14\xb4\xd7 |\x94|-\x19\xec']},  # noqa: E501
            'RegisterNotary',
        ),
        (
            # Too many data in log
            {'type': 'mined', 'logIndex': 0, 'transactionIndex': 0, 'transactionHash': b'\xda\xb8:\xe5\x86\xe9Q\xf2\x9c\xc6<g\x9bl\x84\x85\xf4\x1dh\xce\x8d\xe6\xc0D\xa0*E\xd8m\xd4\x01\xcf', 'blockHash': b'\x13\xa97d\r\x90t\xe5;\x84\xf9\xe0\xb8\xf2c\x1c}\x88\xbf\x84DN\xa0\x16Q\xd9|\xa1\x00\x91\xc0\xbd', 'blockNumber': 25, 'address': '0xf4F1600B0a65995833854738764b50A4DA8d6BE1', 'data': '0x0000000000000000000000000000000000000000000000000000000000000005000000000000000000000000000000000000000000000000000000000000000a00000000000000000000000000000000000000000000000000000000000000ff', 'topics': [b'B\xccp\x0f[x\xa7Le \xecSA\xd7\xc4\x9e\xea\xa8\xf8\x90\x15\xe7\x14\xb4\xd7 |\x94|-\x19\xec', b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00~_ER\t\x1ai\x12]]\xfc\xb7\xb8\xc2e\x90)9[\xdf']},  # noqa: E501
            'DeregisterNotary',
        ),
        (
            # Too few data in log
            {'type': 'mined', 'logIndex': 0, 'transactionIndex': 0, 'transactionHash': b'\xda\xb8:\xe5\x86\xe9Q\xf2\x9c\xc6<g\x9bl\x84\x85\xf4\x1dh\xce\x8d\xe6\xc0D\xa0*E\xd8m\xd4\x01\xcf', 'blockHash': b'\x13\xa97d\r\x90t\xe5;\x84\xf9\xe0\xb8\xf2c\x1c}\x88\xbf\x84DN\xa0\x16Q\xd9|\xa1\x00\x91\xc0\xbd', 'blockNumber': 25, 'address': '0xf4F1600B0a65995833854738764b50A4DA8d6BE1', 'data': '0x0000000000000000000000000000000000000000000000000000000000000001', 'topics': [b'$\xa5\x146ipE\xb9:y\xa2\xbd\xa9\x00\xb0PU\xf1\xe1\xe9\x1b\x02\x1bL/\xb6\xf6|\xbb\x0b.\x95', b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00']},  # noqa: E501
            'AddHeader',
        ),
    )
)
def test_log_parser_with_wrong_log_content(raw_log, event_name):
    with pytest.raises(LogParsingError):
        LogParser(event_name=event_name, log=raw_log)


def test_status_checking_functions(smc_handler):  # noqa: F811
    w3 = smc_handler.web3
    config = get_sharding_testing_config()
    log_handler = LogHandler(w3=w3, period_length=config['PERIOD_LENGTH'])
    shard_tracker = ShardTracker(
        config=config,
        shard_id=0,
        log_handler=log_handler,
        smc_handler_address=smc_handler.address,
    )

    # Register nine notaries
    batch_register(smc_handler, 0, 8)
    # Check that registration log was/was not emitted accordingly
    assert shard_tracker.is_notary_registered(notary=NotaryAccount(0).checksum_address)
    assert shard_tracker.is_notary_registered(notary=NotaryAccount(5).checksum_address)
    assert not shard_tracker.is_notary_registered(notary=NotaryAccount(9).checksum_address)
    fast_forward(smc_handler, 1)

    # Check that add header log has not been emitted yet
    current_period = w3.eth.blockNumber // config['PERIOD_LENGTH']
    assert not shard_tracker.is_new_header_added(period=current_period)
    # Add header in multiple shards
    CHUNK_ROOT_1_0 = b'\x10' * 32
    smc_handler.add_header(
        period=current_period,
        shard_id=0,
        chunk_root=CHUNK_ROOT_1_0,
        private_key=NotaryAccount(0).private_key
    )
    CHUNK_ROOT_1_7 = b'\x17' * 32
    smc_handler.add_header(
        period=current_period,
        shard_id=7,
        chunk_root=CHUNK_ROOT_1_7,
        private_key=NotaryAccount(7).private_key
    )
    CHUNK_ROOT_1_3 = b'\x13' * 32
    smc_handler.add_header(
        period=current_period,
        shard_id=3,
        chunk_root=CHUNK_ROOT_1_3,
        private_key=NotaryAccount(3).private_key
    )
    mine(w3, 1)
    # Check that add header log was successfully emitted
    assert shard_tracker.is_new_header_added(period=current_period)

    # Check that there has not been enough votes yet in shard 0
    assert not shard_tracker.has_enough_vote(period=current_period)
    # Submit three votes in shard 0 and one vote in shard 7
    for sample_index in range(3):
        pool_index = sampling(smc_handler, 0)[sample_index]
        smc_handler.submit_vote(
            period=current_period,
            shard_id=0,
            chunk_root=CHUNK_ROOT_1_0,
            index=sample_index,
            private_key=NotaryAccount(pool_index).private_key
        )
        mine(w3, 1)
    sample_index = 0
    pool_index = sampling(smc_handler, 7)[sample_index]
    smc_handler.submit_vote(
        period=current_period,
        shard_id=7,
        chunk_root=CHUNK_ROOT_1_7,
        index=sample_index,
        private_key=NotaryAccount(pool_index).private_key
    )
    mine(w3, 1)
    # Check that there has not been enough votes yet in shard 0
    # Only three votes in shard 0 while four is required
    assert not shard_tracker.has_enough_vote(period=current_period)
    # Cast the fourth vote
    sample_index = 3
    pool_index = sampling(smc_handler, 0)[sample_index]
    smc_handler.submit_vote(
        period=current_period,
        shard_id=0,
        chunk_root=CHUNK_ROOT_1_0,
        index=sample_index,
        private_key=NotaryAccount(pool_index).private_key
    )
    mine(w3, 1)
    # Check that there are enough votes now in shard 0
    assert shard_tracker.has_enough_vote(period=current_period)
    # Proceed to next period
    fast_forward(smc_handler, 1)

    # Go back and check the status of header and vote counts in last period
    current_period = w3.eth.blockNumber // config['PERIOD_LENGTH']
    assert shard_tracker.is_new_header_added(period=(current_period - 1))
    assert shard_tracker.has_enough_vote(period=(current_period - 1))

    # Deregister
    smc_handler.deregister_notary(private_key=NotaryAccount(0).private_key)
    mine(w3, 1)
    # Check that deregistration log was/was not emitted accordingly
    assert shard_tracker.is_notary_deregistered(NotaryAccount(0).checksum_address)
    assert not shard_tracker.is_notary_deregistered(NotaryAccount(5).checksum_address)

    # Fast foward to end of lock up
    fast_forward(smc_handler, smc_handler.config['NOTARY_LOCKUP_LENGTH'] + 1)
    # Release
    smc_handler.release_notary(private_key=NotaryAccount(0).private_key)
    mine(w3, 1)
    # Check that log was successfully emitted
    assert shard_tracker.is_notary_released(NotaryAccount(0).checksum_address)
