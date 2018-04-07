import rlp
from rlp.sedes import (
    big_endian_int,
)

from eth_utils import (
    keccak,
    to_dict,
    encode_hex,
)

from evm.constants import (
    ZERO_ADDRESS,
    EMPTY_SHA3,
)
from evm.utils.numeric import (
    int_to_bytes32,
)
from evm.utils.padding import (
    pad32,
)
from evm.exceptions import (
    ValidationError,
)
from evm.rlp.sedes import (
    address,
    hash32,
)

from typing import (
    Tuple,
    Iterator,
    Any
)


class CollationHeader(rlp.Serializable):
    fields = [
        ("shard_id", big_endian_int),
        ("expected_period_number", big_endian_int),
        ("period_start_prevhash", hash32),
        ("parent_hash", hash32),
        ("transaction_root", hash32),
        ("coinbase", address),
        ("state_root", hash32),
        ("receipt_root", hash32),
        ("number", big_endian_int),
    ]

    def __init__(self,
                 shard_id: int,
                 expected_period_number: int,
                 period_start_prevhash: bytes,
                 parent_hash: bytes,
                 number: int,
                 transaction_root: bytes=EMPTY_SHA3,
                 coinbase: bytes=ZERO_ADDRESS,
                 state_root: bytes=EMPTY_SHA3,
                 receipt_root: bytes=EMPTY_SHA3,
                 sig: bytes=b'') -> None:
        super(CollationHeader, self).__init__(
            shard_id=shard_id,
            expected_period_number=expected_period_number,
            period_start_prevhash=period_start_prevhash,
            parent_hash=parent_hash,
            transaction_root=transaction_root,
            coinbase=coinbase,
            state_root=state_root,
            receipt_root=receipt_root,
            number=number,
        )

    def __repr__(self) -> str:
        return "<CollationHeader #{0} {1} (shard #{2})>".format(
            self.expected_period_number,
            encode_hex(self.hash)[2:10],
            self.shard_id,
        )

    @property
    def hash(self) -> bytes:
        header_hash = keccak(
            b''.join((
                int_to_bytes32(self.shard_id),
                int_to_bytes32(self.expected_period_number),
                self.period_start_prevhash,
                self.parent_hash,
                self.transaction_root,
                pad32(self.coinbase),
                self.state_root,
                self.receipt_root,
                int_to_bytes32(self.number),
            ))
        )
        return pad32(header_hash[6:])

    @classmethod
    @to_dict
    def _deserialize_header_bytes_to_dict(cls, header_bytes: bytes) -> Iterator[Tuple[str, Any]]:
        # assume all fields are padded to 32 bytes
        obj_size = 32
        if len(header_bytes) != obj_size * len(cls.fields):
            raise ValidationError(
                "Expected header bytes to be of length: {0}. Got length {1} instead.\n- {2}".format(
                    obj_size * len(cls.fields),
                    len(header_bytes),
                    encode_hex(header_bytes),
                )
            )
        for idx, field in enumerate(cls.fields):
            field_name, field_type = field
            start_index = idx * obj_size
            field_bytes = header_bytes[start_index:(start_index + obj_size)]
            if field_type == big_endian_int:
                # remove the leading zeros, to avoid `not minimal length` error in deserialization
                formatted_field_bytes = field_bytes.lstrip(b'\x00')
            elif field_type == address:
                formatted_field_bytes = field_bytes[-20:]
            else:
                formatted_field_bytes = field_bytes
            yield field_name, field_type.deserialize(formatted_field_bytes)

    @classmethod
    def from_bytes(cls, header_bytes: bytes) -> 'CollationHeader':
        header_kwargs = cls._deserialize_header_bytes_to_dict(header_bytes)
        header = cls(**header_kwargs)
        return header
