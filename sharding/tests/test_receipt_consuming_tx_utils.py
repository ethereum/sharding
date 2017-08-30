import pytest

from ethereum import utils, vm
from ethereum.slogging import configure_logging
from ethereum.transactions import Transaction

from sharding.tools import tester as t
from sharding.receipt_consuming_tx_utils import is_receipt_consuming_tx_valid, send_msg_transfer_value
from sharding.used_receipt_store_utils import get_urs_ct, get_urs_contract, mk_initiating_txs_for_urs
from sharding.validator_manager_utils import get_valmgr_addr, get_valmgr_ct

config_string = 'sharding.rctx:debug'
configure_logging(config_string=config_string)

def mk_testing_receipt_consuming_tx(receipt_id, to_addr, value, data=b''):
    startgas = 300000
    tx = Transaction(0, t.GASPRICE, startgas, to_addr, value, data)
    tx.v, tx.r, tx.s = 1, receipt_id, 0
    return tx


@pytest.fixture
def c():
    chain = t.Chain(env='sharding', deploy_sharding_contracts=True)
    chain.mine(5)
    return chain


def test_receipt_consuming_transaction(c):
    valmgr = t.ABIContract(c, get_valmgr_ct(), get_valmgr_addr())

    to_addr = utils.privtoaddr(utils.sha3("test_to_addr"))
    data = b''

    # # test the case when the to_addr is a contract_address
    # k0_valcode_addr = c.tx(t.k0, '', 0, mk_validation_code(t.a0))
    # to_addr = k0_valcode_addr
    # msg_hash = utils.sha3("test_msg")
    # sig = sign(msg_hash, t.k0)
    # data = utils.sha3("test_msg1") + sig

    # registre receipts in mainchain
    shard_id = 0
    valmgr.tx_to_shard(to_addr, shard_id, b'', sender=t.k0, value=1)
    value = 500000
    receipt_id = valmgr.tx_to_shard(to_addr, shard_id, data, sender=t.k0, value=value)

    # Setup the environment in shard `shard_id` #################
    # create the contract USED_RECEIPT_STORE in shard `shard_id`
    c.add_test_shard(shard_id)
    shard0_state = c.shard_head_state[shard_id]
    txs = mk_initiating_txs_for_urs(t.k0, shard0_state.get_nonce(t.a0), shard_id)
    for tx in txs:
        c.direct_tx(tx, shard_id=shard_id)
    urs0 = t.ABIContract(c, get_urs_ct(shard_id), get_urs_contract(shard_id)['addr'], shard_id=shard_id)
    receipt_id = 1
    c.mine(1)
    assert not urs0.get_used_receipts(receipt_id)
    c.mine(1)

    tx = mk_testing_receipt_consuming_tx(receipt_id, to_addr, value)
    if is_receipt_consuming_tx_valid(c.head_state, shard0_state, shard_id, tx):
        send_msg_transfer_value(c.head_state, shard0_state, shard_id, tx)

    assert urs0.get_used_receipts(receipt_id)
