from vyper import compiler

from sharding.contracts.utils.smc_utils import (
    get_smc_json,
    get_smc_source_code,
)


def test_compile_smc():
    compiled_smc_json = get_smc_json()

    vmc_code = get_smc_source_code()
    abi = compiler.mk_full_signature(vmc_code)
    bytecode = compiler.compile(vmc_code)
    bytecode_hex = '0x' + bytecode.hex()

    assert abi == compiled_smc_json["abi"]
    assert bytecode_hex == compiled_smc_json["bytecode"]
