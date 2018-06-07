#!/usr/bin/env python
# -*- coding: utf-8 -*-
from setuptools import setup, find_packages


# requirements
INSTALL_REQUIRES = list()
with open('requirements.txt') as f:
    INSTALL_REQUIRES = f.read().splitlines()

setup(
    name='sharding',
    # *IMPORTANT*: Don't manually change the version here. Use the 'bumpversion' utility.
    version='0.0.2-alpha.1',
    description='Ethereum Sharding Manager Contract',
    url='https://github.com/ethereum/sharding',
    packages=find_packages(
        exclude=[
            "tests",
            "tests.*",
            "tools",
            "docs",
        ]
    ),
    python_requires='>=3.5, <4',
    py_modules=['sharding'],
    setup_requires=['setuptools-markdown'],
    long_description_markdown_filename='README.md',
    include_package_data=True,
    data_files=[('sharding', ['sharding/contracts/sharding_manager.json'])],
    zip_safe=False,
    classifiers=[
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    install_requires=INSTALL_REQUIRES,
)
