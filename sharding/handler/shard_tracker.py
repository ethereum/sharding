from web3 import Web3

from typing import (
    Any,
    Dict,
    Generator,
    List,
    Optional,
    Union,
    Tuple,
)

from eth_utils import (
    encode_hex,
    to_list,
    is_address,
)
from eth_typing import (
    Address,
)

from sharding.contracts.utils.config import (
    get_sharding_config,
)
from sharding.handler.log_handler import (
    LogHandler,
)
from sharding.handler.utils.log_parser import LogParser
from sharding.handler.utils.shard_tracker_utils import (
    to_log_topic_address,
    get_event_signature_from_abi,
)


class ShardTracker:
    """Track emitted logs of specific shard.
    """

    def __init__(self,
                 w3: Web3,
                 config: Optional[Dict[str, Any]],
                 shard_id: int,
                 smc_handler_address: Address) -> None:
        if config is None:
            self.config = get_sharding_config()
        else:
            self.config = config
        self.shard_id = shard_id
        self.log_handler = LogHandler(w3, self.config['PERIOD_LENGTH'])
        self.smc_handler_address = smc_handler_address

    def _get_logs_by_shard_id(self,
                              event_name: str,
                              from_block: Union[int, str]=None,
                              to_block: Union[int, str]=None) -> List[Dict[str, Any]]:
        """Search logs by the shard id.
        """
        return self.log_handler.get_logs(
            address=self.smc_handler_address,
            topics=[
                encode_hex(get_event_signature_from_abi(event_name)),
                encode_hex(self.shard_id.to_bytes(32, byteorder='big')),
            ],
            from_block=from_block,
            to_block=to_block,
        )

    def _get_logs_by_notary(self,
                            event_name: str,
                            notary: Union[str, None],
                            from_block: Union[int, str]=None,
                            to_block: Union[int, str]=None) -> List[Dict[str, Any]]:
        """Search logs by notary address.

        NOTE: The notary address provided must be padded to 32 bytes
        and also hex-encoded. If notary address provided
        is `None`, it will return all logs related to the event.
        """
        return self.log_handler.get_logs(
            address=self.smc_handler_address,
            topics=[
                encode_hex(get_event_signature_from_abi(event_name)),
                notary,
            ],
            from_block=from_block,
            to_block=to_block,
        )

    def _decide_period_block_number(self,
                                    from_period: Union[int, None],
                                    to_period: Union[int, None]
                                    ) -> Tuple[Union[int, None], Union[int, None]]:
        if from_period is None:
            from_block = None
        else:
            from_block = from_period * self.config['PERIOD_LENGTH']

        if to_period is None:
            to_block = None
        else:
            to_block = (to_period + 1) * self.config['PERIOD_LENGTH'] - 1

        return from_block, to_block

    #
    # Basic functions to get emitted logs
    #
    @to_list
    def get_register_notary_logs(self,
                                 from_period: int=None,
                                 to_period: int=None) -> Generator[LogParser, None, None]:
        from_block, to_block = self._decide_period_block_number(from_period, to_period)
        logs = self._get_logs_by_notary(
            'RegisterNotary',
            notary=None,
            from_block=from_block,
            to_block=to_block,
        )
        for log in logs:
            yield LogParser(event_name='RegisterNotary', log=log)

    @to_list
    def get_deregister_notary_logs(self,
                                   from_period: int=None,
                                   to_period: int=None
                                   ) -> Generator[LogParser, None, None]:
        from_block, to_block = self._decide_period_block_number(from_period, to_period)
        logs = self._get_logs_by_notary(
            'DeregisterNotary',
            notary=None,
            from_block=from_block,
            to_block=to_block,
        )
        for log in logs:
            yield LogParser(event_name='DeregisterNotary', log=log)

    @to_list
    def get_release_notary_logs(self,
                                from_period: int=None,
                                to_period: int=None
                                ) -> Generator[LogParser, None, None]:
        from_block, to_block = self._decide_period_block_number(from_period, to_period)
        logs = self._get_logs_by_notary(
            'ReleaseNotary',
            notary=None,
            from_block=from_block,
            to_block=to_block,
        )
        for log in logs:
            yield LogParser(event_name='ReleaseNotary', log=log)

    @to_list
    def get_add_header_logs(self,
                            from_period: int=None,
                            to_period: int=None
                            ) -> Generator[LogParser, None, None]:
        from_block, to_block = self._decide_period_block_number(from_period, to_period)
        logs = self._get_logs_by_shard_id(
            'AddHeader',
            from_block=from_block,
            to_block=to_block,
        )
        for log in logs:
            yield LogParser(event_name='AddHeader', log=log)

    @to_list
    def get_submit_vote_logs(self,
                             from_period: int=None,
                             to_period: int=None
                             ) -> Generator[LogParser, None, None]:
        from_block, to_block = self._decide_period_block_number(from_period, to_period)
        logs = self._get_logs_by_shard_id(
            'SubmitVote',
            from_block=from_block,
            to_block=to_block,
        )
        for log in logs:
            yield LogParser(event_name='SubmitVote', log=log)

    #
    # Functions for user to check the status of registration or votes
    #
    def is_notary_registered(self, notary: str, from_period: int=None) -> bool:
        assert is_address(notary)
        from_block, _ = self._decide_period_block_number(from_period, None)
        log = self._get_logs_by_notary(
            'RegisterNotary',
            notary=to_log_topic_address(notary),
            from_block=from_block,
        )
        return False if not log else True

    def is_notary_deregistered(self, notary: str, from_period: int=None) -> bool:
        assert is_address(notary)
        from_block, _ = self._decide_period_block_number(from_period, None)
        log = self._get_logs_by_notary(
            'DeregisterNotary',
            notary=to_log_topic_address(notary),
            from_block=from_block,
        )
        return False if not log else True

    def is_notary_released(self, notary: str, from_period: int=None) -> bool:
        assert is_address(notary)
        from_block, _ = self._decide_period_block_number(from_period, None)
        log = self._get_logs_by_notary(
            'ReleaseNotary',
            notary=to_log_topic_address(notary),
            from_block=from_block,
        )
        return False if not log else True

    def is_new_header_added(self, period: int) -> bool:
        # Get the header added in the specified period
        log = self._get_logs_by_shard_id(
            'AddHeader',
            from_block=period * self.config['PERIOD_LENGTH'],
            to_block=(period + 1) * self.config['PERIOD_LENGTH'] - 1,
        )
        return False if not log else True

    def has_enough_vote(self, period: int) -> bool:
        # Get the votes submitted in the specified period
        logs = self._get_logs_by_shard_id(
            'SubmitVote',
            from_block=period * self.config['PERIOD_LENGTH'],
            to_block=(period + 1) * self.config['PERIOD_LENGTH'] - 1,
        )
        return False if not logs else len(logs) >= self.config['QUORUM_SIZE']
