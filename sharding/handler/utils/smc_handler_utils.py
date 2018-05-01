
from eth_utils import (
    is_canonical_address,
    to_checksum_address,
    to_dict,
)


@to_dict
def make_call_context(sender_address,
                      gas,
                      value=None,
                      gas_price=None,
                      data=None):
    """
    Makes the context for message call.
    """
    if not is_canonical_address(sender_address):
        raise ValueError('sender_address should be provided in the canonical format')
    if not (isinstance(gas, int) and gas > 0):
        raise ValueError('gas should be provided as positive integer')
    # Both 'from' and 'gas' are required in eth_tester
    yield 'from', to_checksum_address(sender_address)
    yield 'gas', gas
    if value is not None:
        yield 'value', value
    if gas_price is not None:
        yield 'gas_price', gas_price
    if data is not None:
        yield 'data', data


@to_dict
def make_transaction_context(nonce,
                             gas,
                             chain_id=None,
                             value=None,
                             gas_price=None,
                             data=None):
    """
    Makes the context for transaction call.
    """

    if not (isinstance(nonce, int) and nonce >= 0):
        raise ValueError('nonce should be provided as non-negative integer')
    if not (isinstance(gas, int) and gas > 0):
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
