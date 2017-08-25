#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
from setuptools import setup, find_packages


# requirements
INSTALL_REQUIRES_REPLACEMENTS = {
    'git+git://github.com/ethereum/viper.git@master#egg=viper': 'viper',
}
INSTALL_REQUIRES = list()
with open('requirements.txt') as requirements_file:
    for requirement in requirements_file:
        dependency = INSTALL_REQUIRES_REPLACEMENTS.get(
            requirement.strip(),
            requirement.strip(),
        )

        INSTALL_REQUIRES.append(dependency)

INSTALL_REQUIRES = list(set(INSTALL_REQUIRES))

DEPENDENCY_LINKS = []
if os.environ.get("USE_PYETHEREUM_DEVELOP"):
    # Force installation of specific commits of pyethereum.
    pyethereum_ref = '4e945e2a24554ec04eccb160cff689a82eed7e0d'
    DEPENDENCY_LINKS = [
        'http://github.com/ethereum/pyethereum/tarball/%s#egg=ethereum-9.99.9' % pyethereum_ref
    ]

# Force installation of specific commits of viper.
# viper_ref = 'fd7529e7faa6d3aebd8e0e893a42e43c562a56f5'  # Jul 30, 2017
viper_ref = 'fb7333abd7e6460a0ebfea1ecc8a24d2e0f478d2'  # Aug 14, 2017
DEPENDENCY_LINKS.append('http://github.com/ethereum/viper/tarball/%s#egg=viper-9.99.9' % viper_ref)

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
    zip_safe=False,
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
