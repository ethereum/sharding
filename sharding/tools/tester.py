import types
import rlp
from rlp.sedes import List, binary

from ethereum import utils
from ethereum.utils import sha3, privtoaddr, int_to_addr, to_string, checksum_encode, int_to_big_endian, encode_hex
from ethereum.genesis_helpers import mk_basic_state
from ethereum.transactions import Transaction
from ethereum.consensus_strategy import get_consensus_strategy
from ethereum.config import config_homestead, config_tangerine, config_spurious, config_metropolis, default_config, Env
from ethereum.pow.ethpow import Miner
from ethereum.messages import apply_transaction
from ethereum.common import mk_block_from_prevstate, set_execution_results
from ethereum.meta import make_head_candidate
from ethereum.abi import ContractTranslator

from sharding.main_chain import MainChain
from sharding.shard_chain import ShardChain
from sharding.config import sharding_config
from sharding.collator import create_collation
from sharding import state_transition as shard_state_transition
from sharding import used_receipt_store_utils, validator_manager_utils
from sharding.collation import CollationHeader
from sharding.receipt_consuming_tx_utils import apply_shard_transaction
from sharding.validator_manager_utils import ADD_HEADER_TOPIC, call_valmgr

# Initialize accounts
accounts = []
keys = []

for account_number in range(10):
    keys.append(sha3(to_string(account_number)))
    accounts.append(privtoaddr(keys[-1]))

k0, k1, k2, k3, k4, k5, k6, k7, k8, k9 = keys[:10]
a0, a1, a2, a3, a4, a5, a6, a7, a8, a9 = accounts[:10]

base_alloc = {}
minimal_alloc = {}
for a in accounts:
    base_alloc[a] = {'balance': 1000 * utils.denoms.ether}
for i in range(1, 9):
    base_alloc[int_to_addr(i)] = {'balance': 1}
    minimal_alloc[int_to_addr(i)] = {'balance': 1}
minimal_alloc[accounts[0]] = {'balance': 1 * utils.denoms.ether}

# Initialize languages
languages = {}

from ethereum.tools._solidity import get_solidity
_solidity = get_solidity()
if _solidity:
    languages['solidity'] = _solidity

try:
    from viper import compiler
    languages['viper'] = compiler
except ImportError:
    pass


class TransactionFailed(Exception):
    pass


STARTGAS = 3141592
GASPRICE = 1


# from ethereum.slogging import configure_logging
# config_string = 'sharding.shard_chain:debug'
# configure_logging(config_string=config_string)


class ABIContract(object):  # pylint: disable=too-few-public-methods
    def __init__(self, _chain, _abi, address, shard_id=None):
        self.address = address

        if isinstance(_abi, ContractTranslator):
            abi_translator = _abi
        else:
            abi_translator = ContractTranslator(_abi)

        self.translator = abi_translator

        for function_name in self.translator.function_data:
            function = self.method_factory(_chain, function_name, shard_id)
            method = types.MethodType(function, self)
            setattr(self, function_name, method)

    @staticmethod
    def method_factory(test_chain, function_name, shard_id=None):
        """ Return a proxy for calling a contract method with automatic encoding of
        argument and decoding of results.
        """

        def kall(self, *args, **kwargs):
            key = kwargs.get('sender', k0)

            result = test_chain.tx(  # pylint: disable=protected-access
                sender=key,
                to=self.address,
                value=kwargs.get('value', 0),
                data=self.translator.encode(function_name, args),
                startgas=kwargs.get('startgas', STARTGAS),
                shard_id=shard_id
            )

            if result is False:
                return result
            if result == b'':
                return None
            o = self.translator.decode(function_name, result)
            return o[0] if len(o) == 1 else o
        return kall


def get_env(env):
    d = {
        None: config_spurious,
        'mainnet': default_config,
        'homestead': config_homestead,
        'tangerine': config_tangerine,
        'spurious': config_spurious,
        'metropolis': config_metropolis,
        'sharding': sharding_config
    }
    return env if isinstance(env, Env) else Env(config=d[env])


class Chain(object):
    def __init__(self, alloc=None, env=None, deploy_sharding_contracts=False, genesis=None):
        # MainChain
        if genesis is None:
            genesis = mk_basic_state(
                base_alloc if alloc is None else alloc,
                None,
                get_env(env))
        self.chain = MainChain(
            genesis=genesis,
            reset_genesis=True
        )
        self.cs = get_consensus_strategy(self.chain.env.config)
        self.block = mk_block_from_prevstate(self.chain, timestamp=self.chain.state.timestamp + 1)
        self.head_state = self.chain.state.ephemeral_clone()
        self.cs.initialize(self.head_state, self.block)
        self.last_sender = None
        self.last_tx = None

        # ShardChains
        self.collation = {}
        self.shard_head_state = {}
        self.shard_last_sender = {}
        self.shard_last_tx = {}
        self.add_header_logs = []

        # validator manager contract and other pre-compiled contracts
        self.is_sharding_contracts_deployed = False
        if deploy_sharding_contracts:
            self.is_sharding_contracts_deployed = True
            self.deploy_initializing_contracts(k0)
            self.last_sender = k0
            self.mine(1)

    def direct_tx(self, transaction, shard_id=None):
        if shard_id is None:
            self.last_tx, self.last_sender = transaction, None
            success, output = apply_transaction(self.head_state, transaction)
            self.block.transactions.append(transaction)
        else:
            self.shard_last_tx[shard_id], self.shard_last_sender[shard_id] = transaction, None
            assert self.chain.has_shard(shard_id)
            success, output = apply_shard_transaction(
                self.head_state, self.shard_head_state[shard_id], shard_id, transaction
            )
            self.collation[shard_id].transactions.append(transaction)

        if not success:
            raise TransactionFailed()
        return output

    def tx(self, sender=k0, to=b'\x00' * 20, value=0, data=b'', startgas=STARTGAS, gasprice=GASPRICE, shard_id=None):
        sender_addr = privtoaddr(sender)
        if shard_id is None:
            transaction = Transaction(
                self.head_state.get_nonce(sender_addr), gasprice, startgas, to, value, data
            ).sign(sender)
            self.last_sender = sender
        else:
            assert self.chain.has_shard(shard_id)
            transaction = Transaction(
                self.shard_head_state[shard_id].get_nonce(sender_addr), gasprice, startgas, to, value, data
            ).sign(sender)
            self.shard_last_sender[shard_id] = sender
        o = self.direct_tx(transaction, shard_id=shard_id)
        return o

    def contract(self, sourcecode, args=[], sender=k0, value=0, language='evm', startgas=STARTGAS, gasprice=GASPRICE, shard_id=None):
        if language == 'evm':
            assert len(args) == 0
            return self.tx(sender=sender, to=b'', value=value, data=sourcecode, startgas=startgas, gasprice=gasprice, shard_id=shard_id)
        else:
            compiler = languages[language]
            interface = compiler.mk_full_signature(sourcecode)
            ct = ContractTranslator(interface)
            code = compiler.compile(sourcecode) + (ct.encode_constructor_arguments(args) if args else b'')
            addr = self.tx(sender=sender, to=b'', value=value, data=code, startgas=startgas, gasprice=gasprice, shard_id=shard_id)
            return ABIContract(self, ct, addr, shard_id=shard_id)

    def mine(self, number_of_blocks=1, coinbase=a0):
        self.cs.finalize(self.head_state, self.block)
        set_execution_results(self.head_state, self.block)
        self.block = Miner(self.block).mine(rounds=100, start_nonce=0)
        assert self.chain.add_block(self.block)
        b = self.block

        # Reorganize head collation
        collation = None
        # Check add_header_logs
        for item in self.add_header_logs:
            # [num, num, bytes32, bytes32, bytes32, address, bytes32, bytes32, bytes]
            # use sedes to prevent integer 0 from being decoded as b''
            sedes = List([utils.big_endian_int, utils.big_endian_int, utils.hash32, utils.hash32, utils.hash32, utils.address, utils.hash32, utils.hash32, binary])
            values = rlp.decode(item, sedes)
            shard_id = values[0]
            if shard_id in self.chain.shard_id_list:
                collation_hash = sha3(item)
                collation = self.chain.shards[shard_id].get_collation(collation_hash)
        self.chain.reorganize_head_collation(b, collation)
        # Clear logs
        self.add_header_logs = []

        for i in range(1, number_of_blocks):
            b, _ = make_head_candidate(self.chain, parent=b, timestamp=self.chain.state.timestamp + 14, coinbase=coinbase)
            b = Miner(b).mine(rounds=100, start_nonce=0)
            assert self.chain.add_block(b)
            self.chain.reorganize_head_collation(b, None)

        self.change_head(b.header.hash, coinbase)
        return b

    def change_head(self, parent, coinbase=a0):
        self.head_state = self.chain.mk_poststate_of_blockhash(parent).ephemeral_clone()
        self.block = mk_block_from_prevstate(self.chain, self.head_state, timestamp=self.chain.state.timestamp, coinbase=coinbase)
        self.head_state.log_listeners = self.chain.state.log_listeners
        self.cs.initialize(self.head_state, self.block)

    def snapshot(self):
        self.head_state.commit()
        return self.head_state.snapshot(), len(self.block.transactions), self.block.number

    def revert(self, snapshot):
        state_snapshot, txcount, blknum = snapshot
        assert blknum == self.block.number
        self.block.transactions = self.block.transactions[:txcount]
        self.head_state.revert(state_snapshot)

    def __init_shard_var(self, shard_id):
        """Initial shard tester variables
        """
        # Initial collation parameters
        expected_period_number = self.chain.get_expected_period_number()
        self.set_collation(shard_id, expected_period_number, self.chain.shards[shard_id].env.config['GENESIS_PREVHASH'])

        self.shard_last_sender[shard_id] = None
        self.shard_last_tx[shard_id] = None

        # Append log_listeners
        add_header_topic = utils.big_endian_to_int(ADD_HEADER_TOPIC)

        def header_event_watcher(log):
            if log.topics[0] == add_header_topic:
                self.add_header_logs.append(log.data)
        self.head_state.log_listeners.append(header_event_watcher)

    def _get_period_start_prevhash(self, expected_period_number):
        # If it's on forked chain, we can't use get_blockhash_by_number.
        # So try to get period_start_prevhash by message call
        if self.is_sharding_contracts_deployed:
            period_start_prevhash = call_valmgr(self.head_state,
                'get_period_start_prevhash', [expected_period_number]
            )
        else:
            period_start_prevhash = self.chain.get_period_start_prevhash(expected_period_number)
        return period_start_prevhash

    def set_collation(self, shard_id, expected_period_number, parent_collation_hash=None, coinbase=a0):
        """Set collation before building some transactions on the shard chain

        Set `self.shard_head_state` to the integration of "collation-state of parent_collation_hash" and "block-state of period_start_prevblock"
        Set `self.collation` fields
        """
        assert self.chain.has_shard(shard_id)
        if parent_collation_hash is None:
            parent_collation_hash = self.chain.shards[shard_id].head_hash

        # Initialize state: clear and update self.shard_head_state[shard_id] with period_start_prevblock env variables
        self.shard_head_state[shard_id] = self.chain.shards[shard_id].mk_poststate_of_collation_hash(parent_collation_hash).ephemeral_clone()
        period_start_prevhash = self._get_period_start_prevhash(expected_period_number)
        period_start_prevblock = self.chain.get_block(period_start_prevhash)
        assert period_start_prevblock is not None
        self.cs.initialize(self.shard_head_state[shard_id], period_start_prevblock)
        collation = shard_state_transition.mk_collation_from_prevstate(self.chain.shards[shard_id], self.shard_head_state[shard_id], coinbase=coinbase)

        # Initialize collation, set expected_period_number, period_start_prevhash and parent_collation_hash
        collation.header.expected_period_number = expected_period_number
        collation.header.period_start_prevhash = period_start_prevhash
        collation.header.parent_collation_hash = parent_collation_hash
        self.collation[shard_id] = collation

    def add_test_shard(self, shard_id, setup_urs_contracts=True, alloc=None):
        """Initial shard with fake accounts
        """
        assert not self.chain.has_shard(shard_id)

        initial_state = mk_basic_state(
            base_alloc if alloc is None else alloc,
            None, self.chain.env)
        initial_state.delta_balance(
            used_receipt_store_utils.get_urs_contract(shard_id)['addr'],
            (10 ** 9) * utils.denoms.ether
        )
        initial_state.commit()
        shard = ShardChain(shard_id=shard_id, initial_state=initial_state)
        self.chain.add_shard(shard)
        self.__init_shard_var(shard_id)
        if setup_urs_contracts:
            self.setup_and_deploy_urs_contracts(k0, shard_id)

    def generate_shard_tx(self, shard_id, sender=k0, to=b'\x00' * 20, value=0, data=b'', startgas=STARTGAS, gasprice=GASPRICE):
        """Generate a tx of shard
        """
        sender_addr = privtoaddr(sender)
        transaction = Transaction(self.shard_head_state[shard_id].get_nonce(sender_addr), gasprice, startgas,
                                  to, value, data).sign(sender)
        return transaction

    def generate_collation(self, shard_id, coinbase, key, txqueue=None, parent_collation_hash=None, expected_period_number=None):
        """Generate collation
        """
        assert self.chain.has_shard(shard_id)
        if parent_collation_hash is None:
            parent_collation_hash = self.chain.shards[shard_id].head_hash
        if expected_period_number is None:
            expected_period_number = self.chain.get_expected_period_number()
        return create_collation(
            self.chain,
            shard_id,
            parent_collation_hash,
            expected_period_number,
            coinbase,
            key,
            txqueue=txqueue)

    def sharding_valcode_addr(self, privkey):
        """Generate validation code address
        """
        addr = privtoaddr(privkey)
        valcode = validator_manager_utils.mk_validation_code(addr)
        tx = validator_manager_utils.create_contract_tx(self.head_state, privkey, valcode)
        valcode_addr = self.direct_tx(tx)
        self.last_sender = privkey
        return valcode_addr

    def sharding_deposit(self, privkey, validation_code_addr):
        """Deposit
        """
        tx = validator_manager_utils.call_deposit(
            self.head_state, privkey,
            validator_manager_utils.DEPOSIT_SIZE,
            validation_code_addr,
            utils.privtoaddr(privkey))
        self.direct_tx(tx)
        self.last_sender = privkey

    def sharding_withdraw(self, privkey, validator_index):
        """Withdraw
        """
        signature = validator_manager_utils.sign(validator_manager_utils.WITHDRAW_HASH, privkey)
        tx = validator_manager_utils.call_withdraw(
            self.head_state,
            privkey,
            0,
            validator_index,
            signature
        )
        self.direct_tx(tx)
        self.last_sender = privkey

    def collate(self, shard_id, privkey, coinbase=a0):
        """Collate the collation and send a collation-header-transaction
        """
        # Finalize
        assert self.chain.has_shard(shard_id)
        shard_state_transition.finalize(self.shard_head_state[shard_id], coinbase)
        shard_state_transition.set_execution_results(self.shard_head_state[shard_id], self.collation[shard_id])

        # Sign the collation
        collation = self.collation[shard_id]
        collation.header.sig = validator_manager_utils.sign(collation.signing_hash, privkey)

        # Add collation to db
        period_start_prevblock = self.chain.get_block(self.collation[shard_id].header.period_start_prevhash)
        assert self.chain.shards[shard_id].add_collation(collation, period_start_prevblock, self.chain.handle_ignored_collation)

        # Create and send add_header tx
        tx = validator_manager_utils.call_tx_add_header(
            self.head_state, privkey, 0, rlp.encode(CollationHeader.serialize(collation.header)))
        self.direct_tx(tx)
        self.last_sender = privkey

        return collation

    def deploy_initializing_contracts(self, sender_privkey):
        """Deploy rlp_decoder, sighasher and validator_manager contracts
        """
        sender_addr = utils.privtoaddr(sender_privkey)
        txs = validator_manager_utils.mk_initiating_contracts(sender_privkey, self.head_state.get_nonce(sender_addr))
        for tx in txs:
            self.direct_tx(tx)

    def setup_and_deploy_urs_contracts(self, sender_privkey, shard_id):
        """Deploy urs contract and its dependency
        """
        state = self.shard_head_state[shard_id]

        if used_receipt_store_utils.is_urs_setup(state, shard_id):
            return
        txs = used_receipt_store_utils.mk_initiating_txs_for_urs(
            sender_privkey,
            state.get_nonce(utils.privtoaddr(sender_privkey)),
            shard_id
        )
        for tx in txs:
            self.direct_tx(tx, shard_id=shard_id)
        self.shard_last_tx[shard_id], self.shard_last_sender[shard_id] = txs[-1], None

def int_to_0x_hex(v):
    o = encode_hex(int_to_big_endian(v))
    if o and o[0] == '0':
        return '0x' + o[1:]
    else:
        return '0x' + o


def mk_state_test_prefill(c):
    env = {
        "currentCoinbase": checksum_encode(c.head_state.block_coinbase),
        "currentDifficulty": int_to_0x_hex(c.head_state.block_difficulty),
        "currentGasLimit": int_to_0x_hex(c.head_state.gas_limit),
        "currentNumber": int_to_0x_hex(c.head_state.block_number),
        "currentTimestamp": int_to_0x_hex(c.head_state.timestamp),
        "previousHash": "0x"+encode_hex(c.head_state.prev_headers[0].hash),
    }
    pre = c.head_state.to_dict()
    return {"env": env, "pre": pre}


def mk_state_test_postfill(c, prefill, filler_mode=False):
    txdata = c.last_tx.to_dict()
    modified_tx_data = {
        "data": [txdata["data"]],
        "gasLimit": [int_to_0x_hex(txdata["startgas"])],
        "gasPrice": int_to_0x_hex(txdata["gasprice"]),
        "nonce": int_to_0x_hex(txdata["nonce"]),
        "secretKey": '0x' + encode_hex(c.last_sender),
        "to": txdata["to"],
        "value": [int_to_0x_hex(txdata["value"])],
    }
    c.head_state.commit()
    postStateHash = '0x' + encode_hex(c.head_state.trie.root_hash)
    if c.chain.config == config_homestead:
        config = 'Homestead'
    elif c.chain.config == config_tangerine:
        config = 'EIP150'
    elif c.chain.config == config_spurious or c.chain.config == sharding_config:
        config = 'EIP158'
    elif c.chain.config == config_metropolis:
        config = 'Metropolis'
    else:
        raise Exception("Cannot get config")
    o = {
        "env": prefill["env"],
        "pre": prefill["pre"],
        "transaction": modified_tx_data,
    }
    if not filler_mode:
        o["post"] = {config: [{"hash": postStateHash, "indexes": {"data": 0, "gas": 0, "value": 0}}]}
    else:
        o["expect"] = [{"indexes": {"data": 0, "gas": 0, "value": 0}, "network": ["Metropolis"], "result": c.head_state.to_dict()}]
    return o
