import logging

import pytest

from sharding.handler.smc_handler import (
    make_call_context,
    make_transaction_context,
)


ZERO_ADDR = b'\x00' * 20

logger = logging.getLogger('evm.chain.sharding.mainchain_handler.SMCHandler')


def test_make_transaction_context():
    transaction_context = make_transaction_context(
        nonce=0,
        gas=10000,
    )
    assert 'nonce' in transaction_context
    assert 'gas' in transaction_context
    assert 'chainId' in transaction_context
    with pytest.raises(ValueError):
        transaction_context = make_transaction_context(
            nonce=None,
            gas=10000,
        )
    with pytest.raises(ValueError):
        transaction_context = make_transaction_context(
            nonce=0,
            gas=None,
        )


def test_make_call_context():
    call_context = make_call_context(
        sender_address=ZERO_ADDR,
        gas=1000,
    )
    assert 'from' in call_context
    assert 'gas' in call_context
    with pytest.raises(ValueError):
        call_context = make_call_context(
            sender_address=ZERO_ADDR,
            gas=None,
        )
    with pytest.raises(ValueError):
        call_context = make_call_context(
            sender_address=None,
            gas=1000,
        )
