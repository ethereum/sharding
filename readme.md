# Sharding

[![Build Status](https://travis-ci.org/ethereum/sharding.svg?branch=develop)](https://travis-ci.org/ethereum/sharding)

This repository contains the basic sharding utils.

See the "docs" directory for documentation and EIPs, and the "sharding" directory for code.

## Installation
### Environment
Please refer to [pyethereum - Developer-Notes](https://github.com/ethereum/pyethereum/wiki/Developer-Notes)

### Install
```shell
git clone https://github.com/ethereum/sharding/
cd sharding
python setup.py install
```
 
### Install with specific pyethereum branch and commit hash
1. Update `setup.py`
2. Set flag
```shell
USE_PYETHEREUM_DEVELOP=1 python setup.py develop
```

### Install development tool
```shell
pip install -r dev_requirements.txt
```
