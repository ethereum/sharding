from ethereum import utils
from ethereum.messages import apply_transaction
from ethereum.tools import tester as t
from ethereum.transactions import Transaction

from sharding.validator_manager_utils import call_deposit, call_sample, call_validation_code, call_withdraw, get_valmgr_addr, mk_initiating_contracts, mk_validation_code, sign, GASPRICE, STARTGAS

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


def test_contract_utils():
    deposit_size = 10 ** 20
    withdraw_hash = utils.sha3("withdraw")
    valmgr_sender_privkey = t.k0
    c = t.Chain()
    c.mine(1, coinbase=t.a0)
    state = c.head_state
    state.gas_limit = 10 ** 10
    state.set_balance(address=t.a0, value=deposit_size * 10)
    state.set_balance(address=t.a1, value=deposit_size * 10)

    deploy_initializing_contracts(t.k0, state)
    validator_manager_addr = get_valmgr_addr()
    k0_valcode_addr = deploy_contract(state, t.k0, mk_validation_code(t.a0))
    tx = call_deposit(state, validator_manager_addr, t.k0, deposit_size, k0_valcode_addr, t.a2)
    deploy_tx(state, tx)
    assert hex(utils.big_endian_to_int(k0_valcode_addr)) == \
           hex(utils.big_endian_to_int(call_sample(state, validator_manager_addr, 0)))
    tx = call_withdraw(state, validator_manager_addr, t.k0, 0, sign(withdraw_hash, t.k0))
    deploy_tx(state, tx)
    assert 0 == utils.big_endian_to_int(call_sample(state, validator_manager_addr, 0))
    assert call_validation_code(state, k0_valcode_addr, withdraw_hash, sign(withdraw_hash, t.k0))
