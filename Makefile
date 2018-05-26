# Variables
# compile-smc parameters
compile_script = tools/vyper_compile_script.py
contract = sharding/contracts/validator_manager.v.py
contract_json = sharding/contracts/validator_manager.json

# Using target:prerequisites to avoid redundant compilation.
$(contract_json): $(contract)
	python $(compile_script) $(contract)

# Commands
help:
	@echo "compile-smc - compile sharding manager contract"

compile-smc: $(contract_json)
