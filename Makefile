help:
	@echo "clean-build - compile sharding manager contract"

compile-smc:
	python tools/vyper_compile_script.py sharding/contracts/validator_manager.v.py
