#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
from setuptools import setup, find_packages


# requirements
INSTALL_REQUIRES_REPLACEMENTS = {}
INSTALL_REQUIRES = list()
with open('requirements.txt') as requirements_file:
    for requirement in requirements_file:
        # install_requires will break on git URLs, so skip them
        if 'git+' in requirement:
            continue
        dependency = INSTALL_REQUIRES_REPLACEMENTS.get(
            requirement.strip(),
            requirement.strip(),
        )

        INSTALL_REQUIRES.append(dependency)

INSTALL_REQUIRES = list(set(INSTALL_REQUIRES))

DEPENDENCY_LINKS = []
if os.environ.get("USE_PYETHEREUM_DEVELOP"):
    # Force installation of specific commits of pyethereum.
    pyethereum_ref = '85efc8688a3adb45cf9e74fa17022ca4df3ad16a'
    DEPENDENCY_LINKS = [
        'http://github.com/ethereum/pyethereum/tarball/%s#egg=ethereum-9.99.9' % pyethereum_ref,
        'https://github.com/ethereum/serpent/tarball/develop#egg=ethereum-serpent'
    ]


# *IMPORTANT*: Don't manually change the version here. Use the 'bumpversion' utility.
# see: https://github.com/ethereum/pyethapp/wiki/Development:-Versions-and-Releases
version = '0.0.1'

setup(
    name='sharding',
    version=version,
    description='Ethereum Sharding PoC utilities',
    url='https://github.com/ethereum/sharding',
    packages=find_packages("."),
    package_data={},
    classifiers=[
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
    ],
    install_requires=INSTALL_REQUIRES,
    dependency_links=DEPENDENCY_LINKS
)
