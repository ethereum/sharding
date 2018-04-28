import json
import os


DIR = os.path.dirname(__file__)


def get_smc_source_code():
    file_path = os.path.join(DIR, '../validator_manager.v.py')
    smc_source_code = open(file_path).read()
    return smc_source_code


def get_smc_json():
    file_path = os.path.join(DIR, '../validator_manager.json')
    smc_json_str = open(file_path).read()
    return json.loads(smc_json_str)
