from eth_utils import (
    encode_hex,
    to_list,
    is_address,
    to_checksum_address,
)

from sharding.contracts.utils.config import (
    get_sharding_config,
)
from sharding.handler.utils.shard_tracker_utils import (
    parse_register_notary_log,
    parse_deregister_notary_log,
    parse_release_notary_log,
    parse_add_header_log,
    parse_submit_vote_log,
    get_event_signature_from_abi,
)


class ShardTracker:
    """Track emitted logs of specific shard.
    """

    def __init__(self, config, shard_id, log_handler, smc_handler_address):
        if config is None:
            self.config = get_sharding_config()
        else:
            self.config = config
        self.shard_id = shard_id
        self.log_handler = log_handler
        self.smc_handler_address = smc_handler_address

    def _get_logs_by_shard_id(self, event_name, from_block=None, to_block=None):
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

    def _get_logs_by_notary(self, event_name, notary, from_block=None, to_block=None):
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

    #
    # Basic functions to get emitted logs
    #
    @to_list
    def get_register_notary_logs(self):
        logs = self._get_logs_by_notary(event_name='RegisterNotary', notary=None)
        for log in logs:
            yield parse_register_notary_log(log)

    @to_list
    def get_deregister_notary_logs(self):
        logs = self._get_logs_by_notary(event_name='DeregisterNotary', notary=None)
        for log in logs:
            yield parse_deregister_notary_log(log)

    @to_list
    def get_release_notary_logs(self):
        logs = self._get_logs_by_notary(event_name='ReleaseNotary', notary=None)
        for log in logs:
            yield parse_release_notary_log(log)

    @to_list
    def get_add_header_logs(self):
        logs = self._get_logs_by_shard_id(event_name='AddHeader')
        for log in logs:
            yield parse_add_header_log(log)

    @to_list
    def get_submit_vote_logs(self):
        logs = self._get_logs_by_shard_id(event_name='SubmitVote')
        for log in logs:
            yield parse_submit_vote_log(log)

    #
    # Functions for user to check the status of registration or votes
    #
    def is_notary_registered(self, notary):
        assert is_address(notary)
        # Normalize the notary address and padded to 32 bytes
        normalized_address = '0x' + to_checksum_address(notary)[2:].rjust(64, '0')
        log = self._get_logs_by_notary(event_name='RegisterNotary', notary=normalized_address)
        return False if not log else True

    def is_notary_deregistered(self, notary):
        assert is_address(notary)
        # Normalize the notary address and padded to 32 bytes
        normalized_address = '0x' + to_checksum_address(notary)[2:].rjust(64, '0')
        log = self._get_logs_by_notary(event_name='DeregisterNotary', notary=normalized_address)
        return False if not log else True

    def is_notary_released(self, notary):
        assert is_address(notary)
        # Normalize the notary address and padded to 32 bytes
        normalized_address = '0x' + to_checksum_address(notary)[2:].rjust(64, '0')
        log = self._get_logs_by_notary(event_name='ReleaseNotary', notary=normalized_address)
        return False if not log else True

    def is_new_header_added(self, period):
        # Get the header added in the specified period
        log = self._get_logs_by_shard_id(
            event_name='AddHeader',
            from_block=period * self.config['PERIOD_LENGTH'],
            to_block=(period + 1) * self.config['PERIOD_LENGTH'] - 1,
        )
        return False if not log else True

    def has_enough_vote(self, period):
        # Get the votes submitted in the specified period
        logs = self._get_logs_by_shard_id(
            event_name='SubmitVote',
            from_block=period * self.config['PERIOD_LENGTH'],
            to_block=(period + 1) * self.config['PERIOD_LENGTH'] - 1,
        )
        return False if not logs else len(logs) >= self.config['QUORUM_SIZE']
