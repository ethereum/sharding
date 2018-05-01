import pytest

from web3 import (
    Web3,
)

from web3.providers.eth_tester import (
    EthereumTesterProvider,
)

from eth_utils import (
    to_checksum_address,
)

from eth_tester import (
    EthereumTester,
)

from eth_tester.backends.pyevm import (
    PyEVMBackend,
)

from eth_tester.backends.pyevm.main import (
    get_default_account_keys,
)

from sharding.handler.smc_handler import (
    SMCHandler,
)
from sharding.contracts.utils.smc_utils import (
    get_smc_json,
)
from sharding.handler.utils.web3_utils import (
    get_code,
)
from tests.handler.utils.deploy import (
    deploy_smc_contract,
)
from tests.handler.utils.config import (
    get_sharding_testing_config,
)


@pytest.fixture
def smc_handler():
    eth_tester = EthereumTester(
        backend=PyEVMBackend(),
        auto_mine_transactions=False,
    )
    provider = EthereumTesterProvider(eth_tester)
    w3 = Web3(provider)
    if hasattr(w3.eth, "enable_unaudited_features"):
        w3.eth.enable_unaudited_features()

    default_privkey = get_default_account_keys()[0]
    # deploy smc contract
    smc_addr = deploy_smc_contract(
        w3,
        get_sharding_testing_config()['GAS_PRICE'],
        default_privkey,
    )
    assert get_code(w3, smc_addr) != b''

    # setup smc_handler's web3.eth.contract instance
    smc_json = get_smc_json()
    smc_abi = smc_json['abi']
    smc_bytecode = smc_json['bytecode']
    SMCHandlerClass = SMCHandler.factory(w3, abi=smc_abi, bytecode=smc_bytecode)
    smc_handler = SMCHandlerClass(
        to_checksum_address(smc_addr),
        default_privkey=default_privkey,
        config=get_sharding_testing_config(),
    )

    return smc_handler
