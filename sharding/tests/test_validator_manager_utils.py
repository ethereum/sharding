import pytest
import rlp

from ethereum import utils

from sharding.tools import tester as t
from sharding.contract_utils import (
    sign,
    create_contract_tx,
)
from sharding.validator_manager_utils import (
    DEPOSIT_SIZE,
    WITHDRAW_HASH,
    mk_validation_code,
    call_deposit,
    call_validation_code,
    call_valmgr,
    call_withdraw,
    call_tx_add_header,
    call_tx_to_shard,
    call_contract_constantly,
    get_shard_list,
    get_valmgr_addr,
    get_valmgr_ct
)
from sharding.config import sharding_config


config_string = ":info,:debug"
'''
from ethereum.slogging import LogRecorder, configure_logging, set_level
config_string = ':info,eth.vm.log:trace,eth.vm.op:trace,eth.vm.stack:trace,eth.vm.exit:trace,eth.pb.msg:trace,eth.pb.tx:debug'
configure_logging(config_string=config_string)
'''


num_blocks = 6


@pytest.fixture()
def chain():
    """A initialized chain from ethereum.tester.Chain
    """
    c = t.Chain()
    c.head_state.set_balance(address=t.a0, value=DEPOSIT_SIZE * 10)
    c.head_state.set_balance(address=t.a1, value=DEPOSIT_SIZE * 10)
    c.mine(number_of_blocks=num_blocks - 1, coinbase=t.a0)
    c.deploy_initializing_contracts(t.k0)
    c.mine(number_of_blocks=1, coinbase=t.a0)
    return c


def test_call_deposit_withdraw_sample(chain):
    # make validation code
    k0_valcode = mk_validation_code(t.a0)
    tx = create_contract_tx(chain.head_state, t.k0, k0_valcode)
    k0_valcode_addr = chain.direct_tx(tx)
    chain.mine(1)

    # deposit
    tx = call_deposit(chain.head_state, t.k0, DEPOSIT_SIZE, k0_valcode_addr, t.a2)
    chain.direct_tx(tx)
    chain.mine(sharding_config['SHUFFLING_CYCLE_LENGTH'])
    assert hex(utils.big_endian_to_int(k0_valcode_addr)) == call_valmgr(chain.head_state, 'sample', [0])

    shard_list = get_shard_list(chain.head_state, k0_valcode_addr)
    assert shard_list[0]

    # withdraw
    tx = call_withdraw(chain.head_state, t.k0, 0, 0, sign(WITHDRAW_HASH, t.k0))
    chain.direct_tx(tx)
    chain.mine(1)
    assert 0 == int(call_valmgr(chain.head_state, 'sample', [0]), 16)
    assert call_validation_code(chain.head_state, k0_valcode_addr, WITHDRAW_HASH, sign(WITHDRAW_HASH, t.k0))


def test_call_add_header_get_shard_head(chain):
    def get_colhdr(shard_id, parent_collation_hash, number, collation_coinbase=t.a0, privkey=t.k0, n_blocks=num_blocks):
        period_length = 5
        expected_period_number = (n_blocks + 1) // period_length
        b = chain.chain.get_block_by_number(expected_period_number * period_length - 1)
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

    # register t.k0 as the validators
    tx = create_contract_tx(chain.head_state, t.k0, mk_validation_code(t.a0))
    k0_valcode_addr = chain.direct_tx(tx)
    chain.mine(1)
    tx2 = create_contract_tx(chain.head_state, t.k1, mk_validation_code(t.a1))
    k1_valcode_addr = chain.direct_tx(tx2)
    chain.mine(1)

    tx = call_deposit(chain.head_state, t.k0, DEPOSIT_SIZE, k0_valcode_addr, t.a0)
    chain.direct_tx(tx)
    chain.mine(sharding_config['SHUFFLING_CYCLE_LENGTH'])
    tx = call_deposit(chain.head_state, t.k1, DEPOSIT_SIZE, k1_valcode_addr, t.a1)
    chain.direct_tx(tx)
    chain.mine(sharding_config['SHUFFLING_CYCLE_LENGTH'])

    # sample
    if utils.big_endian_to_int(k0_valcode_addr) == int(call_valmgr(chain.head_state, 'sample', [0]), 16):
        privkey = t.k0
        collator_addr = t.a0
    else:
        privkey = t.k1
        collator_addr = t.a1

    # create collation header
    shard0_genesis_colhdr_hash = utils.encode_int32(0)
    colhdr = get_colhdr(0, shard0_genesis_colhdr_hash, 1, collation_coinbase=collator_addr, privkey=privkey, n_blocks=chain.chain.head.number)
    colhdr_hash = utils.sha3(colhdr)
    assert call_valmgr(chain.head_state, 'get_shard_head', [0]) == shard0_genesis_colhdr_hash

    # message call test
    assert call_valmgr(chain.head_state, 'add_header', [colhdr], sender_addr=t.a0)

    # transaction call test
    # `add_header` verifies whether the colhdr is signed by the current
    # selected validator, using `sample`
    tx = call_tx_add_header(chain.head_state, privkey, 0, colhdr)
    chain.direct_tx(tx)
    chain.mine(1)

    assert colhdr_hash == call_valmgr(chain.head_state, 'get_shard_head', [0])


def test_call_tx_to_shard(chain):
    state = chain.head_state
    tx = call_tx_to_shard(state, t.k0, 10, t.a1, 0, 100000, 1, b'')
    output = chain.direct_tx(tx)
    assert 0 == utils.big_endian_to_int(output)


# def test_valmgr_addr_in_sharding_config():
#     assert sharding_config['VALIDATOR_MANAGER_ADDRESS'] == \
#         utils.checksum_encode(get_valmgr_addr())


def test_sign():
    """Test collator.sign(msg_hash, privkey)
    """
    msg_hash = utils.sha3('hello')
    privkey = t.k0
    assert sign(msg_hash, privkey) == b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x1bz\x05\x13\xf6\xa4\xbb\x0c\xaf<\x87\x95\xa7\xf5\x139\x84\x89\\#\x91\x15\x9dPX\x9e\xc9\x01\x8fp\x14\xd2,\x0c\x97\xd6\xbf\xc9\x11\x9d\xf7Z\x99-\xd3\x05\xc6\xf3\xfc\xfbe\x99c1\xcb\x93K\xf0I,\xd7\xebUB%'

    msg_hash2 = utils.sha3('world')
    assert sign(msg_hash2, privkey) == b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x1b\x10\xcf\xacjd\xa9@\xf44\xd5K[A\xbb\xde&0\xc3V\xe4\x9f\xe9+\xf6\'\x0eVbQtYf"5\x04\x85\xc8\x1dB\x92\xd9\xc9r\xed\x9a\x08\xfet\xce@\xa2\x1bm\x88\xc2\x875\xff\x99\xc5oN\xac\xa4'


def test_get_validators_max_index(chain):
    k0_valcode = mk_validation_code(t.a0)
    k1_valcode = mk_validation_code(t.a1)
    tx = create_contract_tx(chain.head_state, t.k0, k0_valcode)
    k0_valcode_addr = chain.direct_tx(tx)
    tx = create_contract_tx(chain.head_state, t.k1, k1_valcode)
    k1_valcode_addr = chain.direct_tx(tx)
    chain.mine(1)

    tx = call_deposit(chain.head_state, t.k0, DEPOSIT_SIZE, k0_valcode_addr, t.a0)
    chain.direct_tx(tx)

    validators_max_index = call_contract_constantly(
        chain.head_state, get_valmgr_ct(), get_valmgr_addr(), 'get_validators_max_index', [],
        value=0, startgas=10 ** 20, sender_addr=t.a0
    )
    assert validators_max_index == 0

    chain.mine(sharding_config['SHUFFLING_CYCLE_LENGTH'])
    validators_max_index = call_contract_constantly(
        chain.head_state, get_valmgr_ct(), get_valmgr_addr(), 'get_validators_max_index', [],
        value=0, startgas=10 ** 20, sender_addr=t.a0
    )
    assert validators_max_index == 1

    tx = call_deposit(chain.head_state, t.k1, DEPOSIT_SIZE, k1_valcode_addr, t.a1)
    chain.direct_tx(tx)
    validators_max_index = call_contract_constantly(
        chain.head_state, get_valmgr_ct(), get_valmgr_addr(), 'get_validators_max_index', [],
        value=0, startgas=10 ** 20, sender_addr=t.a0
    )
    assert validators_max_index == 1

    chain.mine(sharding_config['SHUFFLING_CYCLE_LENGTH'])
    validators_max_index = call_contract_constantly(
        chain.head_state, get_valmgr_ct(), get_valmgr_addr(), 'get_validators_max_index', [],
        value=0, startgas=10 ** 20, sender_addr=t.a0
    )
    assert validators_max_index == 2


def test_call_get_collation_gas_limit(chain):
    output = call_valmgr(chain.head_state, 'get_collation_gas_limit', [])
    assert output == 10000000
