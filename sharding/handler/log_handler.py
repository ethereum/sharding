import logging


class LogHandler:

    logger = logging.getLogger("sharding.handler.LogHandler")

    def __init__(self, web3, period_length):
        self.web3 = web3
        self.period_length = period_length

    def get_logs(
            self,
            *,
            address=None,
            topics=None,
            from_block=None,
            to_block=None):
        current_block_number = self.web3.eth.blockNumber
        if from_block is None:
            # Search from the start of current period
            fromBlock = current_block_number - current_block_number % self.period_length
        else:
            if from_block > current_block_number:
                raise Exception(
                    "Can not search logs starting with block number"
                    "larger than current block number"
                )
            fromBlock = from_block
        if to_block is None:
            toBlock = current_block_number
        else:
            toBlock = min(current_block_number, to_block)

        return self.web3.eth.getLogs(
            {
                # Block number must be integer
                'fromBlock': int(fromBlock),
                'toBlock': int(toBlock),
                'address': address,
                'topics': topics,
            }
        )
