from eth_utils import (
    encode_hex,
    to_list,
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

    def __init__(self, shard_id, log_handler, smc_handler_address):
        self.shard_id = shard_id
        self.log_handler = log_handler
        self.smc_handler_address = smc_handler_address

    def _get_logs_by_shard_id(self, event_name):
        """Search logs by the shard id.
        """
        return self.log_handler.get_new_logs(
            address=self.smc_handler_address,
            topics=[
                encode_hex(get_event_signature_from_abi(event_name)),
                encode_hex(self.shard_id.to_bytes(32, byteorder='big')),
            ],
        )

    def _get_logs_by_notary(self, event_name, notary):
        """Search logs by notary address.

        NOTE: The notary address provided must be padded to 32 bytes
        and also hex-encoded. If notary address provided
        is `None`, it will return all logs related to the event.
        """
        return self.log_handler.get_new_logs(
            address=self.smc_handler_address,
            topics=[
                encode_hex(get_event_signature_from_abi(event_name)),
                notary,
            ],
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
