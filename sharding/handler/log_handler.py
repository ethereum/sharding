import logging


class LogHandler:

    logger = logging.getLogger("sharding.handler.LogHandler")

    def __init__(self, w3, period_length):
        self.w3 = w3
        self.period_length = period_length

    def get_logs(
            self,
            *,
            address=None,
            topics=None,
            from_block=None,
            to_block=None):
        filter_params = {
            'address': address,
            'topics': topics,
        }

        current_block_number = self.w3.eth.blockNumber
        if from_block is None:
            # Search from the start of current period if from_block is not given
            filter_params['fromBlock'] = current_block_number - \
                current_block_number % self.period_length
        else:
            if from_block > current_block_number:
                raise Exception(
                    "Can not search logs starting with block number"
                    "larger than current block number"
                )
            # Block number must be integer
            filter_params['fromBlock'] = int(from_block)

        if to_block is None:
            filter_params['toBlock'] = current_block_number
        else:
            # Block number must be integer
            filter_params['toBlock'] = min(current_block_number, int(to_block))

        return self.w3.eth.getLogs(filter_params)
