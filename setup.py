#!/usr/bin/env python
# -*- coding: utf-8 -*-
from setuptools import setup, find_packages


# requirements
INSTALL_REQUIRES = list()
with open('requirements.txt') as f:
    INSTALL_REQUIRES = f.read().splitlines()

DEPENDENCY_LINKS = []

# Force installation of specific commits of vyper.
# vyper_ref = '044d1565df370cd31c00fc7fb728672647f39cf2'  # Mar 9, 2018
# DEPENDENCY_LINKS.append('http://github.com/ethereum/vyper/tarball/%s#egg=vyper-9.99.9' % vyper_ref)

# *IMPORTANT*: Don't manually change the version here. Use the 'bumpversion' utility.
# see: https://github.com/ethereum/pyethapp/wiki/Development:-Versions-and-Releases
version = '0.0.1'

setup(
    name='sharding',
    version=version,
    description='Ethereum Sharding Manager Contract',
    url='https://github.com/ethereum/sharding',
    packages=find_packages(exclude=["old_sharding_poc"]),
    package_data={},
    zip_safe=False,
    classifiers=[
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    install_requires=INSTALL_REQUIRES,
    dependency_links=DEPENDENCY_LINKS,
)
