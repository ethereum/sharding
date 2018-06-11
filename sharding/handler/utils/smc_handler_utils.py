from typing import (
    Any,
    Generator,
    Tuple,
)

from eth_utils import (
    is_address,
    to_checksum_address,
    to_dict,
)
from eth_typing import (
    Address,
)


@to_dict
def make_call_context(sender_address: Address,
                      gas: int=None,
                      value: int=None,
                      gas_price: int=None,
                      data: bytes=None) -> Generator[Tuple[str, Any], None, None]:
    """
    Makes the context for message call.
    """
    if not is_address(sender_address):
        raise ValueError('Message call sender provided is not an address')
    # 'from' is required in eth_tester
    yield 'from', to_checksum_address(sender_address)
    if gas is not None:
        yield 'gas', gas
    if value is not None:
        yield 'value', value
    if gas_price is not None:
        yield 'gas_price', gas_price
    if data is not None:
        yield 'data', data


@to_dict
def make_transaction_context(nonce: int,
                             gas: int,
                             chain_id: int=None,
                             value: int=None,
                             gas_price: int=None,
                             data: bytes=None) -> Generator[Tuple[str, Any], None, None]:
    """
    Makes the context for transaction call.
    """

    if not (isinstance(nonce, int) and nonce >= 0):
        raise ValueError('nonce should be provided as non-negative integer')
    if not (isinstance(gas, int) and gas >= 0):
        raise ValueError('gas should be provided as positive integer')
    yield 'nonce', nonce
    yield 'gas', gas
    yield 'chainId', chain_id
    if value is not None:
        yield 'value', value
    if gas_price is not None:
        yield 'gasPrice', gas_price
    if data is not None:
        yield 'data', data
