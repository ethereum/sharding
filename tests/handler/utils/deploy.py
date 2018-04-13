import functools

from cytoolz import (
    pipe,
)

from eth_utils import (
    to_canonical_address,
    decode_hex,
)

from evm.utils.numeric import (
    int_to_bytes32,
)
from evm.vm.forks.byzantium.transactions import (
    ByzantiumTransaction,
)

from evm.utils.address import (
    generate_contract_address,
)

from contracts.utils.smc_utils import (
    get_smc_json,
)
from handler.utils.web3_utils import (
    get_nonce,
    send_raw_transaction,
    mine,
)
from tests.handler.utils.config import (
    get_sharding_testing_config,
)


def constructor_arguments():
    """Encode system parameters passed into SMC constructor
    """
    arguments = (
        int_to_bytes32(get_sharding_testing_config()['SHARD_COUNT']) +
        int_to_bytes32(get_sharding_testing_config()['PERIOD_LENGTH']) +
        int_to_bytes32(get_sharding_testing_config()['LOOKAHEAD_PERIODS']) +
        int_to_bytes32(get_sharding_testing_config()['NOTARY_DEPOSIT']) +
        int_to_bytes32(get_sharding_testing_config()['PERIOD_LENGTH'])
    )
    return arguments


def make_deploy_smc_tx(TransactionClass, gas_price):
    smc_json = get_smc_json()
    smc_bytecode = decode_hex(smc_json['bytecode'])
    tx_data = smc_bytecode + constructor_arguments()
    v = 27
    r = 1000000000000000000000000000000000000000000000000000000000000000000000000000
    s = 1000000000000000000000000000000000000000000000000000000000000000000000000000
    return TransactionClass(
        0,
        gas_price,
        3000000,
        b'',
        0,
        tx_data,
        v,
        r,
        s
    )


def get_contract_address_from_deploy_tx(transaction):
    return pipe(
        transaction.sender,
        to_canonical_address,
        functools.partial(generate_contract_address, nonce=0),
    )


def deploy_smc_contract(web3, gas_price, privkey):
    deploy_smc_tx = make_deploy_smc_tx(ByzantiumTransaction, gas_price=gas_price)

    # fund the smc contract deployer
    fund_deployer_tx = ByzantiumTransaction.create_unsigned_transaction(
        get_nonce(web3, privkey.public_key.to_canonical_address()),
        gas_price,
        500000,
        deploy_smc_tx.sender,
        deploy_smc_tx.gas * deploy_smc_tx.gas_price + deploy_smc_tx.value,
        b'',
    ).as_signed_transaction(privkey)
    fund_deployer_tx_hash = send_raw_transaction(web3, fund_deployer_tx)
    mine(web3, 1)
    assert web3.eth.getTransactionReceipt(fund_deployer_tx_hash) is not None

    # deploy smc contract
    deploy_smc_tx_hash = send_raw_transaction(web3, deploy_smc_tx)
    mine(web3, 1)
    assert web3.eth.getTransactionReceipt(deploy_smc_tx_hash) is not None

    return get_contract_address_from_deploy_tx(deploy_smc_tx)
