.PHONY: test lint smoke smoke-wsl install

PYTHON ?= python
WSL ?= wsl -e bash -lc

test:
	$(PYTHON) -m pytest tests/ -q

lint:
	$(PYTHON) -m compileall openanalog -q

# End-to-end ngspice smoke — requires ngspice on PATH (use smoke-wsl on Windows)
smoke:
	$(PYTHON) scripts/smoke_all.py 80

smoke-wsl:
	$(WSL) "cd /mnt/c/Users/oojia/OpenForge && source .venv_wsl/bin/activate && python scripts/smoke_all.py 80"

install:
	pip install -e ".[web]" pytest
