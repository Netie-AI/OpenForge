.PHONY: test lint smoke smoke-wsl install serve serve-wsl

PYTHON ?= python
WSL ?= wsl -e bash -lc
HOST ?= 127.0.0.1
PORT ?= 8080

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

# Launch OpenForge web UI (requires pip install -e ".[web]")
serve:
	$(PYTHON) -m openanalog serve --host $(HOST) --port $(PORT)

serve-wsl:
	$(WSL) "cd /mnt/c/Users/oojia/OpenForge && source .venv_wsl/bin/activate && pip install -e '.[web]' -q && python -m openanalog serve --host $(HOST) --port $(PORT)"
