import pytest
import rlp
from rlp.sedes import List, binary

from ethereum import utils

from sharding.tools import tester as t
from sharding.validator_manager_utils import (
    WITHDRAW_HASH,
    DEPOSIT_SIZE,
    mk_validation_code,
    sign,
    get_valmgr_addr,
    get_valmgr_ct,
    get_valmgr_code,
)

validator_manager_code = get_valmgr_code()


def test_validator_manager():
    # Must pay 100 ETH to become a validator

    c = t.Chain(env='sharding', deploy_sharding_contracts=True)

    k0_valcode_addr = c.tx(t.k0, '', 0, mk_validation_code(t.a0))
    k1_valcode_addr = c.tx(t.k1, '', 0, mk_validation_code(t.a1))

    num_blocks = 11
    c.mine(num_blocks - 1, coinbase=t.a0)
    c.head_state.gas_limit = 10 ** 12

    # deploy valmgr and its prerequisite contracts and transactions
    x = t.ABIContract(c, get_valmgr_ct(), get_valmgr_addr())

    # test deposit: fails when msg.value != DEPOSIT_SIZE
    with pytest.raises(t.TransactionFailed):
        # gas == GASLIMIT
        x.deposit(k0_valcode_addr, k0_valcode_addr)

    # test withdraw: fails when no validator record
    assert not x.withdraw(0, sign(WITHDRAW_HASH, t.k0))

    return_addr = utils.privtoaddr(utils.sha3("return_addr"))

    # test get_shard_list: couldn't be sampled
    assert not x.get_shard_list(k0_valcode_addr)[0]

    # test deposit: works fine
    assert 0 == x.deposit(k0_valcode_addr, return_addr, value=DEPOSIT_SIZE, sender=t.k0)

    # test get_shard_list: can be sampled now
    assert x.get_shard_list(k0_valcode_addr)[0]

    # test sample: correctly sample the only one validator
    assert x.sample(0) == hex(utils.big_endian_to_int(k0_valcode_addr))

    # test withdraw: see if the money is returned
    assert x.withdraw(0, sign(WITHDRAW_HASH, t.k0))
    assert c.head_state.get_balance(return_addr) == DEPOSIT_SIZE

    # test deposit: make use of empty slots
    assert 0 == x.deposit(k0_valcode_addr, return_addr, value=DEPOSIT_SIZE, sender=t.k0)

    # test deposit: other validation code address
    assert 1 == x.deposit(k1_valcode_addr, return_addr, value=DEPOSIT_SIZE, sender=t.k1)
    assert x.withdraw(1, sign(WITHDRAW_HASH, t.k1))
    # test deposit: working fine in the edge condition
    assert 1 == x.deposit(k1_valcode_addr, return_addr, value=DEPOSIT_SIZE, sender=t.k1)

    # test deposit: fails when valcode_addr is deposited before
    with pytest.raises(t.TransactionFailed):
        x.deposit(k1_valcode_addr, return_addr, value=DEPOSIT_SIZE, sender=t.k1)
    # test withdraw: fails when the signature is not corret
    assert not x.withdraw(1, sign(WITHDRAW_HASH, t.k0))

    # test sample: sample returns zero_addr (i.e. 0x00) when there is no depositing validator
    assert x.withdraw(0, sign(WITHDRAW_HASH, t.k0))
    assert x.withdraw(1, sign(WITHDRAW_HASH, t.k1))
    assert x.sample(0) == "0x0000000000000000000000000000000000000000"

    def get_colhdr(shard_id, parent_collation_hash, number, collation_coinbase=t.a0, privkey=t.k0, n_blocks=num_blocks):
        period_length = 5
        expected_period_number = (n_blocks + 1) // period_length
        b = c.chain.get_block_by_number(expected_period_number * period_length - 1)
        period_start_prevhash = b.header.hash
        tx_list_root = b"tx_list " * 4
        post_state_root = b"post_sta" * 4
        receipt_root = b"receipt " * 4
        sighash = utils.sha3(
            rlp.encode([
                shard_id, expected_period_number, period_start_prevhash,
                parent_collation_hash, tx_list_root, collation_coinbase,
                post_state_root, receipt_root, number
            ])
        )
        sig = sign(sighash, privkey)
        return rlp.encode([
            shard_id, expected_period_number, period_start_prevhash,
            parent_collation_hash, tx_list_root, collation_coinbase,
            post_state_root, receipt_root, number, sig
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
                sedes = List([utils.big_endian_int, utils.big_endian_int, utils.hash32, utils.hash32, utils.hash32, utils.address, utils.hash32, utils.hash32, utils.big_endian_int, binary])
                values = rlp.decode(last_log, sedes)
                print("add_header: shard_id={}, expected_period_number={}, header_hash={}, parent_header_hash={}".format(values[0], values[1], utils.sha3(last_log), values[3]))

    c.head_state.log_listeners.append(header_event_watcher)

    shard_id = 0
    shard0_genesis_colhdr_hash = utils.encode_int32(0)

    # test get_shard_head: returns genesis_colhdr_hash when there is no new header
    assert x.get_shard_head() == shard0_genesis_colhdr_hash

    # test get_num_validators: check there's no validator
    assert x.get_num_validators() == 0

    # deposit again
    assert 1 == x.deposit(k0_valcode_addr, return_addr, value=DEPOSIT_SIZE, sender=t.k0)
    assert 0 == x.deposit(k1_valcode_addr, return_addr, value=DEPOSIT_SIZE, sender=t.k1)

    # test: check there's no empty slot
    assert x.get_validators_max_index() == 2
    assert x.get_num_validators() == 2
    assert x.get_is_valcode_deposited(k0_valcode_addr)
    assert x.get_is_valcode_deposited(k1_valcode_addr)

    # test: get collator
    if x.sample(0) == hex(utils.big_endian_to_int(k0_valcode_addr)):
        privkey = t.k0
    elif x.sample(0) == hex(utils.big_endian_to_int(k1_valcode_addr)):
        privkey = t.k1
    else:
        raise Exception("Failed to sample")

    # test add_header: works normally with parent_collation_hash == GENESIS
    h1 = get_colhdr(
        shard_id,
        shard0_genesis_colhdr_hash,
        1,
        collation_coinbase=utils.privtoaddr(privkey),
        privkey=privkey,
        n_blocks=c.chain.head.number
    )
    assert x.add_header(h1)

    # test add_header: fails when the header is added before
    with pytest.raises(t.TransactionFailed):
        h1 = get_colhdr(shard_id, shard0_genesis_colhdr_hash, 1)
        x.add_header(h1)

    # test add_header: fails when the parent_collation_hash is not added before
    with pytest.raises(t.TransactionFailed):
        h2 = get_colhdr(shard_id, utils.sha3("123"), 2)
        x.add_header(h2)
    # test add_header: the log is generated normally

    # TODO: The following tests need to mine before calling add_header,
    # this section may not be appropriate to test the second add_header

    # h2 = get_colhdr(shard_id, h1_hash)
    # h2_hash = utils.sha3(h2)
    # assert x.add_header(h2)
    # latest_log_hash = utils.sha3(header_logs[-1])
    # assert h2_hash == latest_log_hash
    # # test get_shard_head: get the correct head when a new header is added
    # assert x.get_shard_head(0) == h2_hash
    # # test get_shard_head: get the correct head when a fork happened
    # h1_prime = get_colhdr(shard_id, shard0_genesis_colhdr_hash, collation_coinbase=t.a1)
    # h1_prime_hash = utils.sha3(h1_prime)
    # assert x.add_header(h1_prime)
    # h2_prime = get_colhdr(shard_id, h1_prime_hash, collation_coinbase=t.a1)
    # h2_prime_hash = utils.sha3(h2_prime)
    # assert x.add_header(h2_prime)
    # assert x.get_shard_head(0) == h2_hash
    # h3_prime = get_colhdr(shard_id, h2_prime_hash, collation_coinbase=t.a1)
    # h3_prime_hash = utils.sha3(h3_prime)
    # assert x.add_header(h3_prime)
    # assert x.get_shard_head(0) == h3_prime_hash

    '''
    # test get_ancestor: h3_prime's height is too low so and it doesn't have a
    #                    10000th ancestor. So it should fail.
    with pytest.raises(t.TransactionFailed):
        ancestor_10000th_hash = x.get_ancestor(shard_id, h3_prime_hash)
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
        current_colhdr = get_colhdr(shard_id, current_colhdr_hash, collation_coinbase=t.a1)
        assert x.add_header(current_colhdr)
        current_colhdr_hash = utils.sha3(current_colhdr)
    assert x.get_ancestor(shard_id, current_colhdr_hash) == shard0_genesis_colhdr_hash
    '''

    # test tx_to_shard: add request tx and get the receipt id
    to_addr = utils.privtoaddr(utils.sha3("to_addr"))
    startgas = 100000
    gasprice = 1
    receipt_id0 = x.tx_to_shard(to_addr, 0, startgas, gasprice, b'', sender=t.k0, value=100)
    assert 0 == receipt_id0
    # test tx_to_shard: see if receipt_id is incrementing when called
    # multiple times
    receipt_id1 = x.tx_to_shard(to_addr, 0, startgas, gasprice, b'', sender=t.k1, value=101)
    assert 1 == receipt_id1
    assert 101 == x.get_receipts__value(receipt_id1)

    # test update_gasprice: fails when msg.sender doesn't match
    with pytest.raises(t.TransactionFailed):
        x.update_gasprice(receipt_id1, 2, sender=t.k0)
    # test update_gasprice: see if the gasprice updated successfully
    assert x.update_gasprice(receipt_id1, 2, sender=t.k1)
    assert 2 == x.get_receipts__tx_gasprice(receipt_id1)

    print(utils.checksum_encode(get_valmgr_addr()))
