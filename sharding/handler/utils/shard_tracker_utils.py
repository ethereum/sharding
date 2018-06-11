from typing import (
    Union,
)

from eth_utils import (
    event_abi_to_log_topic,
    to_checksum_address,
)
from eth_typing import (
    Address,
)

from sharding.contracts.utils.smc_utils import (
    get_smc_json,
)


def to_log_topic_address(address: Union[Address, str]) -> str:
    return '0x' + to_checksum_address(address)[2:].rjust(64, '0')


def get_event_signature_from_abi(event_name: str) -> bytes:
    for function in get_smc_json()['abi']:
        if function['name'] == event_name and function['type'] == 'event':
            return event_abi_to_log_topic(function)
    raise ValueError("Event with name {} not found".format(event_name))
