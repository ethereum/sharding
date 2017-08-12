import pytest
import rlp

from ethereum import utils
from ethereum.slogging import LogRecorder, configure_logging, set_level
from ethereum.tools import tester as t
from ethereum.transactions import Transaction
from rlp.sedes import List, binary

from sharding.validator_manager_utils import (get_valmgr_addr,
                                              get_valmgr_ct,
                                              get_valmgr_code,
                                              mk_initiating_contracts,
                                              mk_validation_code, sighasher_tx,
                                              sign, viper_rlp_decoder_tx)

config_string = ":info,:debug"
'''
from ethereum.slogging import LogRecorder, configure_logging, set_level
config_string = ':info,eth.vm.log:trace,eth.vm.op:trace,eth.vm.stack:trace,eth.vm.exit:trace,eth.pb.msg:trace,eth.pb.tx:debug'
configure_logging(config_string=config_string)
'''

validator_manager_code = get_valmgr_code()

def test_validator_manager():
    # Must pay 100 ETH to become a validator
    deposit_size = 10 ** 20
    withdraw_msg_hash = utils.sha3("withdraw")

    c = t.Chain()

    k0_valcode_addr = c.tx(t.k0, '', 0, mk_validation_code(t.a0))
    k1_valcode_addr = c.tx(t.k1, '', 0, mk_validation_code(t.a1))

    c.mine(1, coinbase=t.a0)
    c.head_state.gas_limit = 10 ** 12
    c.head_state.set_balance(address=t.a0, value=deposit_size * 10)
    c.head_state.set_balance(address=t.a1, value=deposit_size * 10)

    # deploy valmgr and its prerequisite contracts and transactions
    txs = mk_initiating_contracts(t.k0, c.head_state.get_nonce(t.a0))
    for tx in txs:
        try:
            c.direct_tx(tx)
        except t.TransactionFailed:
            pass
    x = t.ABIContract(c, get_valmgr_ct(), get_valmgr_addr())

    # test deposit: fails when msg.value != deposit_size
    with pytest.raises(t.TransactionFailed):
        x.deposit(k0_valcode_addr, k0_valcode_addr)
    # test withdraw: fails when no validator record
    assert not x.withdraw(0, sign(withdraw_msg_hash, t.k0))
    # test deposit: works fine
    assert 0 == x.deposit(k0_valcode_addr, k0_valcode_addr, value=deposit_size, sender=t.k0)
    assert 1 == x.deposit(k1_valcode_addr, k1_valcode_addr, value=deposit_size, sender=t.k1)
    assert x.withdraw(0, sign(withdraw_msg_hash, t.k0))
    # test deposit: make use of empty slots
    assert 0 == x.deposit(k0_valcode_addr, k0_valcode_addr, value=deposit_size, sender=t.k0)
    assert x.withdraw(1, sign(withdraw_msg_hash, t.k1))
    # test deposit: working fine in the edge condition
    assert 1 == x.deposit(k1_valcode_addr, k1_valcode_addr, value=deposit_size, sender=t.k1)
    # test deposit: fails when valcode_addr is deposited before
    with pytest.raises(t.TransactionFailed):
        x.deposit(k1_valcode_addr, k1_valcode_addr, value=deposit_size, sender=t.k1)
    # test withdraw: fails when the signature is not corret
    assert not x.withdraw(1, sign(withdraw_msg_hash, t.k0))

    # test sample: correctly sample the only one validator
    assert x.withdraw(0, sign(withdraw_msg_hash, t.k0))
    assert x.sample(0) == hex(utils.big_endian_to_int(k1_valcode_addr))
    # test sample: sample returns zero_addr (i.e. 0x00) when there is no depositing validator
    assert x.withdraw(1, sign(withdraw_msg_hash, t.k1))
    assert x.sample(0) == "0x0000000000000000000000000000000000000000"
    assert 1 == x.deposit(k0_valcode_addr, k0_valcode_addr, value=deposit_size, sender=t.k0)

    def get_colhdr(shardId, parent_collation_hash, collation_coinbase=t.a0):
        expected_period_number = 0
        period_start_prevhash = b"period  " * 4
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

    header_logs = []
    add_header_topic = utils.big_endian_to_int(utils.sha3("add_header()"))

    def header_event_watcher(log):
        header_logs, add_header_topic
        # print the last log and store the recent received one
        if log.topics[0] == add_header_topic:
            # print(log.data)
            header_logs.append(log.data)
            if len(header_logs) > 1:
                last_log = header_logs.pop(0)
                # [num, num, bytes32, bytes32, bytes32, address, bytes32, bytes32, bytes]
                # use sedes to prevent integer 0 from being decoded as b''
                sedes = List([utils.big_endian_int, utils.big_endian_int, utils.hash32, utils.hash32, utils.hash32, utils.address, utils.hash32, utils.hash32, binary])
                values = rlp.decode(last_log, sedes)
                print("add_header: shardId={}, expected_period_number={}, header_hash={}, parent_header_hash={}".format(values[0], values[1], utils.sha3(last_log), values[3]))

    c.head_state.log_listeners.append(header_event_watcher)

    # configure_logging(config_string=config_string)
    shardId = 0
    shard0_genesis_colhdr_hash = utils.sha3(utils.encode_int32(shardId) + b"GENESIS")

    # test get_head: returns genesis_colhdr_hash when there is no new header
    assert x.get_head() == shard0_genesis_colhdr_hash
    # test add_header: works normally with parent_collation_hash == GENESIS
    h1 = get_colhdr(shardId, shard0_genesis_colhdr_hash)
    h1_hash = utils.sha3(h1)
    assert x.add_header(h1)
    # test add_header: fails when the header is added before
    with pytest.raises(t.TransactionFailed):
        h1 = get_colhdr(shardId, shard0_genesis_colhdr_hash)
        result = x.add_header(h1)
    # test add_header: fails when the parent_collation_hash is not added before
    with pytest.raises(t.TransactionFailed):
        h2 = get_colhdr(shardId, utils.sha3("123"))
        result = x.add_header(h2)
    # test add_header: the log is generated normally
    h2 = get_colhdr(shardId, h1_hash)
    h2_hash = utils.sha3(h2)
    assert x.add_header(h2)
    latest_log_hash = utils.sha3(header_logs[-1])
    assert h2_hash == latest_log_hash
    # test get_head: get the correct head when a new header is added
    assert x.get_head(0) == h2_hash
    # test get_head: get the correct head when a fork happened
    h1_prime = get_colhdr(shardId, shard0_genesis_colhdr_hash, collation_coinbase=t.a1)
    h1_prime_hash = utils.sha3(h1_prime)
    assert x.add_header(h1_prime)
    h2_prime = get_colhdr(shardId, h1_prime_hash, collation_coinbase=t.a1)
    h2_prime_hash = utils.sha3(h2_prime)
    assert x.add_header(h2_prime)
    assert x.get_head(0) == h2_hash
    h3_prime = get_colhdr(shardId, h2_prime_hash, collation_coinbase=t.a1)
    h3_prime_hash = utils.sha3(h3_prime)
    assert x.add_header(h3_prime)
    assert x.get_head(0) == h3_prime_hash
    '''
    # test get_ancestor: h3_prime's height is too low so and it doesn't have a
    #                    10000th ancestor. So it should fail.
    with pytest.raises(t.TransactionFailed):
        ancestor_10000th_hash = x.get_ancestor(shardId, h3_prime_hash)
    # test get_ancestor:
    # TODO: figure out a better test instead of adding headers one by one.
    #       This test takes few minutes. For now, you can adjust the `kth_ancestor`
    #       to a smaller number here, and the same number of iterations of the `for`
    #       loop in `get_ancestor` in the validator_manager contract.
    current_height = 3 # h3_prime
    kth_ancestor = 10000
    current_colhdr_hash = h3_prime_hash
    # add (kth_ancestor - current_height) headers to get the genesis as the ancestor
    for i in range(kth_ancestor - current_height):
        current_colhdr = get_colhdr(shardId, current_colhdr_hash, collation_coinbase=t.a1)
        assert x.add_header(current_colhdr)
        current_colhdr_hash = utils.sha3(current_colhdr)
    assert x.get_ancestor(shardId, current_colhdr_hash) == shard0_genesis_colhdr_hash
    '''
