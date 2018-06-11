import logging
from typing import (
    Any,
    Dict,
    List,
    Union,
)

from evm.exceptions import BlockNotFound

from web3 import Web3

from eth_typing import (
    Address,
)


class LogHandler:

    logger = logging.getLogger("sharding.handler.LogHandler")

    def __init__(self, w3: Web3, period_length: int) -> None:
        self.w3 = w3
        self.period_length = period_length

    def get_logs(self,
                 address: Address=None,
                 topics: List[Union[str, None]]=None,
                 from_block: Union[int, str]=None,
                 to_block: Union[int, str]=None) -> List[Dict[str, Any]]:
        filter_params = {
            'address': address,
            'topics': topics,
        }  # type: Dict[str, Any]

        current_block_number = self.w3.eth.blockNumber
        if from_block is None:
            # Search from the start of current period if from_block is not given
            filter_params['fromBlock'] = current_block_number - \
                current_block_number % self.period_length
        else:
            if from_block > current_block_number:
                raise BlockNotFound(
                    "Try to search from block number {} while current block number is {}".format(
                        from_block,
                        current_block_number
                    )
                )
            filter_params['fromBlock'] = from_block

        if to_block is None:
            filter_params['toBlock'] = 'latest'
        else:
            filter_params['toBlock'] = min(current_block_number, to_block)

        return self.w3.eth.getLogs(filter_params)
