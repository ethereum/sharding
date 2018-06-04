import pytest

from web3 import (
    Web3,
)

from web3.providers.eth_tester import (
    EthereumTesterProvider,
)

from eth_tester import (
    EthereumTester,
    PyEVMBackend,
)

from eth_tester.backends.pyevm.main import (
    get_default_account_keys,
)
from sharding.handler.smc_handler import (
    SMCHandler as SMCHandlerFactory,
)
from sharding.handler.utils.web3_utils import (
    get_code,
)
from tests.handler.utils.config import (
    get_sharding_testing_config,
)


@pytest.fixture(scope="session")
def smc_testing_config():
    return get_sharding_testing_config()


@pytest.fixture
def smc_handler(smc_testing_config):
    eth_tester = EthereumTester(
        backend=PyEVMBackend(),
        auto_mine_transactions=False,
    )
    provider = EthereumTesterProvider(eth_tester)
    w3 = Web3(provider)
    if hasattr(w3.eth, "enable_unaudited_features"):
        w3.eth.enable_unaudited_features()

    private_key = get_default_account_keys()[0]

    # deploy smc contract
    SMCHandler = w3.eth.contract(ContractFactoryClass=SMCHandlerFactory)
    constructor_kwargs = {
        "_SHARD_COUNT": smc_testing_config["SHARD_COUNT"],
        "_PERIOD_LENGTH": smc_testing_config["PERIOD_LENGTH"],
        "_LOOKAHEAD_LENGTH": smc_testing_config["LOOKAHEAD_PERIODS"],
        "_COMMITTEE_SIZE": smc_testing_config["COMMITTEE_SIZE"],
        "_QUORUM_SIZE": smc_testing_config["QUORUM_SIZE"],
        "_NOTARY_DEPOSIT": smc_testing_config["NOTARY_DEPOSIT"],
        "_NOTARY_LOCKUP_LENGTH": smc_testing_config["NOTARY_LOCKUP_LENGTH"],
    }
    eth_tester.enable_auto_mine_transactions()
    deployment_tx_hash = SMCHandler.constructor(**constructor_kwargs).transact()
    deployment_receipt = w3.eth.waitForTransactionReceipt(deployment_tx_hash, timeout=0)
    eth_tester.disable_auto_mine_transactions()

    assert get_code(w3, deployment_receipt.contractAddress) != b''
    smc_handler = SMCHandler(
        address=deployment_receipt.contractAddress,
        private_key=private_key,
        config=smc_testing_config,
    )

    return smc_handler
