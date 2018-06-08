# Variables
# compile-smc parameters
compile_script = tools/vyper_compile_script.py
contract = sharding/contracts/sharding_manager.v.py
contract_json = sharding/contracts/sharding_manager.json

# Using target:prerequisites to avoid redundant compilation.
$(contract_json): $(contract)
	python $(compile_script) $(contract)

# Commands
help:
	@echo "compile-smc - compile sharding manager contract"
	@echo "clean - remove build and Python file artifacts"
	@echo "clean-build - remove build artifacts"
	@echo "clean-pyc - remove Python file artifacts"
	@echo "lint - check style with flake8 and mypy"
	@echo "test - run tests quickly with the default Python"
	@echo "test-all - run tox"
	@echo "release - package and upload a release"
	@echo "dist - package"

compile-smc: $(contract_json)

clean: clean-build clean-pyc

clean-build:
	rm -fr build/
	rm -fr dist/
	rm -fr *.egg-info

clean-pyc:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +

lint:
	tox -elint3{5,6}

test:
	py.test --tb native tests

test-all:
	tox

release: clean
	CURRENT_SIGN_SETTING=$(git config commit.gpgSign)
	git config commit.gpgSign true
	bumpversion $(bump)
	git push upstream && git push upstream --tags
	python setup.py sdist bdist_wheel upload
	git config commit.gpgSign "$(CURRENT_SIGN_SETTING)"

sdist: clean
	python setup.py sdist bdist_wheel
	ls -l dist
