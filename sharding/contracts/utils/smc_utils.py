import json
import os

from typing import (
    Any,
    Dict,
)


DIR = os.path.dirname(__file__)


def get_smc_source_code() -> str:
    file_path = os.path.join(DIR, '../sharding_manager.v.py')
    smc_source_code = open(file_path).read()
    return smc_source_code


def get_smc_json() -> Dict[str, Any]:
    file_path = os.path.join(DIR, '../sharding_manager.json')
    smc_json_str = open(file_path).read()
    return json.loads(smc_json_str)
