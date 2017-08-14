import pytest
import rlp

from ethereum import utils
from ethereum.messages import apply_transaction
from ethereum.tools import tester as t
from ethereum.transactions import Transaction

from sharding.validator_manager_utils import (GASPRICE, STARTGAS, call_deposit,
                                              call_sample,
                                              call_validation_code,
                                              call_withdraw, call_add_header,
                                              call_get_head,
                                              call_get_collation_gas_limit,
                                              get_valmgr_addr,
                                              mk_initiating_contracts,
                                              mk_validation_code, sign)

deposit_size = 10 ** 20
withdraw_hash = utils.sha3("withdraw")

config_string = ":info,:debug"
'''
from ethereum.slogging import LogRecorder, configure_logging, set_level
config_string = ':info,eth.vm.log:trace,eth.vm.op:trace,eth.vm.stack:trace,eth.vm.exit:trace,eth.pb.msg:trace,eth.pb.tx:debug'
configure_logging(config_string=config_string)
'''

# Testing Part
def deploy_tx(state, tx):
    success, output = apply_transaction(state, tx)
    if not success:
        raise t.TransactionFailed("Failed to deploy tx")
    return output


def deploy_contract(state, sender_privkey, bytecode):
    tx = Transaction(
            state.get_nonce(utils.privtoaddr(sender_privkey)),
            GASPRICE, STARTGAS, to=b'', value=0,
            data=bytecode
    ).sign(sender_privkey)
    return deploy_tx(state, tx)


def deploy_initializing_contracts(sender_privkey, state):
    sender_addr = utils.privtoaddr(sender_privkey)
    txs = mk_initiating_contracts(sender_privkey, state.get_nonce(sender_addr))
    for tx in txs:
        try:
            deploy_tx(state, tx)
        except t.TransactionFailed:
            pass

num_blocks = 6

@pytest.fixture
def chain():
    """A modified head_state from ethereum.tester.Chain.head_state
    """
    c = t.Chain()
    c.mine(num_blocks - 1, coinbase=t.a0)
    c.head_state.gas_limit = 10 ** 12
    c.head_state.set_balance(address=t.a0, value=deposit_size * 10)
    c.head_state.set_balance(address=t.a1, value=deposit_size * 10)
    deploy_initializing_contracts(t.k0, c.head_state)
    return c


def test_call_deposit_withdraw_sample(chain):
    state = chain.head_state
    k0_valcode_addr = deploy_contract(state, t.k0, mk_validation_code(t.a0))
    tx = call_deposit(state, t.k0, deposit_size, k0_valcode_addr, t.a2)
    deploy_tx(state, tx)
    assert hex(utils.big_endian_to_int(k0_valcode_addr)) == \
           hex(utils.big_endian_to_int(call_sample(state, 0)))
    tx = call_withdraw(state, t.k0, 0, 0, sign(withdraw_hash, t.k0))
    deploy_tx(state, tx)
    assert 0 == utils.big_endian_to_int(call_sample(state, 0))
    assert call_validation_code(state, k0_valcode_addr, withdraw_hash, sign(withdraw_hash, t.k0))


def test_call_add_header_get_head(chain):
    state = chain.head_state
    def get_colhdr(shardId, parent_collation_hash, collation_coinbase=t.a0):
        period_length = 5
        expected_period_number = num_blocks // period_length
        b = chain.chain.get_block_by_number(expected_period_number * period_length - 1)
        period_start_prevhash = b.header.hash
        tx_list_root = b"tx_list " * 4
        post_state_root = b"post_sta" * 4
        receipt_root = b"receipt " * 4
        sighash = utils.sha3(
            rlp.encode([
                shardId, expected_period_number, period_start_prevhash,
                parent_collation_hash, tx_list_root, collation_coinbase,
                post_state_root, receipt_root
            ])
        )
        sig = sign(sighash, t.k0)
        return rlp.encode([
            shardId, expected_period_number, period_start_prevhash,
            parent_collation_hash, tx_list_root, collation_coinbase,
            post_state_root, receipt_root, sig
        ])
    shard0_genesis_colhdr_hash = utils.encode_int32(0)
    colhdr = get_colhdr(0, shard0_genesis_colhdr_hash)
    colhdr_hash = utils.sha3(colhdr)
    assert call_get_head(state, 0) == shard0_genesis_colhdr_hash
    # register t.k0 as the validators
    k0_valcode_addr = deploy_contract(state, t.k0, mk_validation_code(t.a0))
    tx = call_deposit(state, t.k0, deposit_size, k0_valcode_addr, t.a2)
    deploy_tx(state, tx)
    # `add_header` verifies whether the colhdr is signed by the current
    # selected validator, using `sample`
    tx = call_add_header(state, t.k0, 0, colhdr)
    deploy_tx(state, tx)
    assert colhdr_hash == call_get_head(state, 0)

