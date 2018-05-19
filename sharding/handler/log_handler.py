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
        if to_block is None:
            toBlock = current_block_number

        return self.web3.eth.getLogs(
            {
                'fromBlock': fromBlock,
                'toBlock': toBlock,
                'address': address,
                'topics': topics,
            }
        )
