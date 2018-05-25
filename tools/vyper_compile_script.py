import argparse
import json
import os

from vyper import compiler


def generate_compiled_json(file_path):
    vmc_code = open(file_path).read()
    abi = compiler.mk_full_signature(vmc_code)
    bytecode = compiler.compile(vmc_code)
    bytecode_hex = '0x' + bytecode.hex()
    contract_json = {
        'abi': abi,
        'bytecode': bytecode_hex,
    }
    # write json
    basename = os.path.basename(file_path)
    dirname = os.path.dirname(file_path)
    contract_name = basename.split('.')[0]
    with open(dirname + "/{}.json".format(contract_name), 'w') as f_write:
        json.dump(contract_json, f_write)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=str, help="the path of the contract")
    args = parser.parse_args()
    path = args.path
    generate_compiled_json(path)


if __name__ == '__main__':
    main()
