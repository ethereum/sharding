import logging

import pytest

from sharding.handler.log_handler import (
    LogHandler,
)
from sharding.handler.shard_tracker import (
    NoCandidateHead,
    ShardTracker,
)
from sharding.handler.utils.shard_tracker_utils import (
    parse_add_header_log,
)

from tests.handler.fixtures import (  # noqa: F401
    smc_handler,
)


logger = logging.getLogger('evm.chain.sharding.mainchain_handler.ShardTracker')


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


@pytest.mark.parametrize(  # noqa: F811
    'mock_score,mock_is_new_head,expected_score,expected_is_new_head',
    (
        # test case in doc.md
        (
            (10, 11, 12, 11, 13, 14, 15, 11, 12, 13, 14, 12, 13, 14, 15, 16, 17, 18, 19, 16),
            (True, True, True, False, True, True, True, False, False, False, False, False, False, False, False, True, True, True, True, False),  # noqa: E501
            (19, 18, 17, 16, 16, 15, 15, 14, 14, 14, 13, 13, 13, 12, 12, 12, 11, 11, 11, 10),
            (True, True, True, True, False, True, False, True, False, False, True, False, False, True, False, False, True, False, False, True),  # noqa: E501
        ),
        (
            (1, 2, 3, 2, 2, 2),
            (True, True, True, False, False, False),
            (3, 2, 2, 2, 2, 1),
            (True, True, False, False, False, True),
        ),
    )
)
def test_shard_tracker_fetch_candidate_head(smc_handler,
                                            mock_score,
                                            mock_is_new_head,
                                            expected_score,
                                            expected_is_new_head):
    shard_id = 0
    log_handler = LogHandler(smc_handler.web3)
    shard_0_tracker = ShardTracker(shard_id, log_handler, smc_handler.address)
    mock_collation_added_logs = [
        {
            'header': [None] * 10,
            'score': mock_score[i],
            'is_new_head': mock_is_new_head[i],
        } for i in range(len(mock_score))
    ]
    # mock collation_added_logs
    shard_0_tracker.new_logs = mock_collation_added_logs
    for i in range(len(mock_score)):
        log = shard_0_tracker.fetch_candidate_head()
        assert log['score'] == expected_score[i]
        assert log['is_new_head'] == expected_is_new_head[i]
    with pytest.raises(NoCandidateHead):
        log = shard_0_tracker.fetch_candidate_head()
