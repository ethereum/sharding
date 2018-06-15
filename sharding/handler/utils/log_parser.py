from typing import (
    Any,
    Dict,
    List,
    Tuple,
    Union,
)

from eth_utils import (
    to_canonical_address,
    decode_hex,
    big_endian_to_int,
)
from eth_typing import (
    Address,
)

from sharding.contracts.utils.smc_utils import (
    get_smc_json,
)
from sharding.handler.exceptions import (
    LogParsingError,
)


class LogParser(object):
    def __init__(self, *, event_name: str, log: Dict[str, Any]) -> None:
        event_abi = self._extract_event_abi(event_name=event_name)

        topics = []
        data = []
        for item in event_abi["inputs"]:
            if item['indexed'] is True:
                topics.append((item['name'], item['type']))
            else:
                data.append((item['name'], item['type']))

        self._set_topic_value(topics=topics, log=log)
        self._set_data_value(data=data, log=log)

    def _extract_event_abi(self, *, event_name: str) -> Dict[str, Any]:
        for func in get_smc_json()['abi']:
            if func['name'] == event_name and func['type'] == 'event':
                return func
        raise LogParsingError("Can not find event {}".format(event_name))

    def _set_topic_value(self, *, topics: List[Tuple[str, Any]], log: Dict[str, Any]) -> None:
        if len(topics) != len(log['topics'][1:]):
            raise LogParsingError(
                "Error parsing log topics, expect"
                "{} topics but get {}.".format(len(topics), len(log['topics'][1:]))
            )
        for (i, topic) in enumerate(topics):
            val = self._parse_value(val_type=topic[1], val=log['topics'][i + 1])
            setattr(self, topic[0], val)

    def _set_data_value(self, *, data: List[Tuple[str, Any]], log: Dict[str, Any]) -> None:
        data_bytes = decode_hex(log['data'])
        if len(data) * 32 != len(data_bytes):
            raise LogParsingError(
                "Error parsing log data, expect"
                "{} data but get {}.".format(len(data), len(data_bytes))
            )
        for (i, (name, type_)) in enumerate(data):
            val = self._parse_value(val_type=type_, val=data_bytes[i * 32: (i + 1) * 32])
            setattr(self, name, val)

    def _parse_value(self, *, val_type: str, val: bytes) -> Union[bool, Address, bytes, int]:
        if val_type == 'bool':
            return bool(big_endian_to_int(val))
        elif val_type == 'address':
            return to_canonical_address(val[-20:])
        elif val_type == 'bytes32':
            return val
        elif 'int' in val_type:
            return big_endian_to_int(val)
        else:
            raise LogParsingError(
                "Error parsing the type of given value. Expect bool/address/bytes32/int*"
                "but get {}.".format(val_type)
            )
