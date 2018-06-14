import logging
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Tuple,
)

from web3.contract import (
    Contract,
)
from eth_utils import (
    decode_hex,
    to_canonical_address,
)

from sharding.handler.utils.smc_handler_utils import (
    make_call_context,
    make_transaction_context,
)
from sharding.contracts.utils.smc_utils import (
    get_smc_json,
)

from eth_keys import (
    datatypes,
)
from eth_typing import (
    Address,
    Hash32,
)


smc_json = get_smc_json()


class SMC(Contract):

    logger = logging.getLogger("sharding.SMC")
    abi = smc_json["abi"]
    bytecode = decode_hex(smc_json["bytecode"])

    default_priv_key = None  # type: datatypes.PrivateKey
    default_sender_address = None  # type: Address
    config = None  # type: Dict[str, Any]

    _estimate_gas_dict = {
        entry['name']: entry['gas']
        for entry in smc_json["abi"]
        if entry['type'] == 'function'
    }  # type: Dict[str, int]

    def __init__(self,
                 *args: Any,
                 default_priv_key: datatypes.PrivateKey,
                 config: Dict[str, Any],
                 **kwargs: Any) -> None:
        self.default_priv_key = default_priv_key
        self.default_sender_address = self.default_priv_key.public_key.to_canonical_address()
        self.config = config

        super().__init__(*args, **kwargs)

    #
    # property
    #
    @property
    def basic_call_context(self) -> Dict[str, Any]:
        return make_call_context(
            sender_address=self.default_sender_address,
        )

    #
    # Public variable getter functions
    #
    def does_notary_exist(self, notary_address: Address) -> bool:
        return self.functions.does_notary_exist(notary_address).call(self.basic_call_context)

    def get_notary_info(self, notary_address: Address) -> Tuple[int, int]:
        return self.functions.get_notary_info(notary_address).call(self.basic_call_context)

    def notary_pool_len(self) -> int:
        return self.functions.notary_pool_len().call(self.basic_call_context)

    def notary_pool(self, pool_index: int) -> List[Address]:
        notary_address = self.functions.notary_pool(pool_index).call(self.basic_call_context)
        return to_canonical_address(notary_address)

    def empty_slots_stack_top(self) -> int:
        return self.functions.empty_slots_stack_top().call(self.basic_call_context)

    def empty_slots_stack(self, stack_index: int) -> List[int]:
        return self.functions.empty_slots_stack(stack_index).call(self.basic_call_context)

    def current_period_notary_sample_size(self) -> int:
        return self.functions.current_period_notary_sample_size().call(self.basic_call_context)

    def next_period_notary_sample_size(self) -> int:
        return self.functions.next_period_notary_sample_size().call(self.basic_call_context)

    def notary_sample_size_updated_period(self) -> int:
        return self.functions.notary_sample_size_updated_period().call(self.basic_call_context)

    def records_updated_period(self, shard_id: int) -> int:
        return self.functions.records_updated_period(shard_id).call(self.basic_call_context)

    def head_collation_period(self, shard_id: int) -> int:
        return self.functions.head_collation_period(shard_id).call(self.basic_call_context)

    def get_member_of_committee(self, shard_id: int, index: int) -> Address:
        notary_address = self.functions.get_member_of_committee(
            shard_id,
            index,
        ).call(self.basic_call_context)
        return to_canonical_address(notary_address)

    def get_collation_chunk_root(self, shard_id: int, period: int) -> Hash32:
        return self.functions.collation_records__chunk_root(
            shard_id,
            period,
        ).call(self.basic_call_context)

    def get_collation_proposer(self, shard_id: int, period: int) -> Address:
        proposer_address = self.functions.collation_records__proposer(
            shard_id,
            period,
        ).call(self.basic_call_context)
        return to_canonical_address(proposer_address)

    def get_collation_is_elected(self, shard_id: int, period: int) -> bool:
        return self.functions.collation_records__is_elected(
            shard_id,
            period,
        ).call(self.basic_call_context)

    def current_vote(self, shard_id: int) -> bytes:
        return self.functions.current_vote(
            shard_id,
        ).call(self.basic_call_context)

    def get_vote_count(self, shard_id: int) -> int:
        return self.functions.get_vote_count(
            shard_id,
        ).call(self.basic_call_context)

    def has_notary_voted(self, shard_id: int, index: int) -> bool:
        return self.functions.has_notary_voted(
            shard_id,
            index,
        ).call(self.basic_call_context)

    def _send_transaction(self,
                          *,
                          func_name: str,
                          args: Iterable[Any],
                          private_key: datatypes.PrivateKey=None,
                          nonce: int=None,
                          chain_id: int=None,
                          gas: int=None,
                          value: int=0,
                          gas_price: int=None,
                          data: bytes=None) -> Hash32:
        if gas_price is None:
            gas_price = self.config['GAS_PRICE']
        if private_key is None:
            private_key = self.private_key
        if nonce is None:
            nonce = self.web3.eth.getTransactionCount(private_key.public_key.to_checksum_address())
        build_transaction_detail = make_transaction_context(
            nonce=nonce,
            gas=gas,
            chain_id=chain_id,
            value=value,
            gas_price=gas_price,
            data=data,
        )
        func_instance = getattr(self.functions, func_name)
        unsigned_transaction = func_instance(*args).buildTransaction(
            transaction=build_transaction_detail,
        )
        signed_transaction_dict = self.web3.eth.account.signTransaction(
            unsigned_transaction,
            private_key.to_hex(),
        )
        tx_hash = self.web3.eth.sendRawTransaction(signed_transaction_dict['rawTransaction'])
        return tx_hash

    #
    # Transactions
    #
    def register_notary(self,
                        private_key: datatypes.PrivateKey=None,
                        gas_price: int=None) -> Hash32:
        gas = self._estimate_gas_dict['register_notary']
        tx_hash = self._send_transaction(
            func_name='register_notary',
            args=[],
            private_key=private_key,
            value=self.config['NOTARY_DEPOSIT'],
            gas=gas,
            gas_price=gas_price,
        )
        return tx_hash

    def deregister_notary(self,
                          private_key: datatypes.PrivateKey=None,
                          gas_price: int=None) -> Hash32:
        gas = self._estimate_gas_dict['deregister_notary']
        tx_hash = self._send_transaction(
            func_name='deregister_notary',
            args=[],
            private_key=private_key,
            gas=gas,
            gas_price=gas_price,
        )
        return tx_hash

    def release_notary(self,
                       private_key: datatypes.PrivateKey=None,
                       gas_price: int=None) -> Hash32:
        gas = self._estimate_gas_dict['release_notary']
        tx_hash = self._send_transaction(
            func_name='release_notary',
            args=[],
            private_key=private_key,
            gas=gas,
            gas_price=gas_price,
        )
        return tx_hash

    def add_header(self,
                   *,
                   shard_id: int,
                   period: int,
                   chunk_root: Hash32,
                   private_key: datatypes.PrivateKey=None,
                   gas_price: int=None) -> Hash32:
        gas = self._estimate_gas_dict['add_header']
        tx_hash = self._send_transaction(
            func_name='add_header',
            args=[
                shard_id,
                period,
                chunk_root,
            ],
            private_key=private_key,
            gas=gas,
            gas_price=gas_price,
        )
        return tx_hash

    def submit_vote(self,
                    *,
                    shard_id: int,
                    period: int,
                    chunk_root: Hash32,
                    index: int,
                    private_key: datatypes.PrivateKey=None,
                    gas_price: int=None) -> Hash32:
        gas = self._estimate_gas_dict['submit_vote']
        tx_hash = self._send_transaction(
            func_name='submit_vote',
            args=[
                shard_id,
                period,
                chunk_root,
                index,
            ],
            private_key=private_key,
            gas=gas,
            gas_price=gas_price,
        )
        return tx_hash
