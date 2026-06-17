.PHONY: test lint smoke smoke-wsl install serve serve-wsl

PYTHON ?= python
WSL_DISTRO ?= Ubuntu
WSL ?= wsl -d $(WSL_DISTRO) -e bash -lc
WSL_ROOT := $(shell wsl -d $(WSL_DISTRO) -e wslpath -u "$(CURDIR)")
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
	$(WSL) "cd '$(WSL_ROOT)' && source .venv_wsl/bin/activate && python scripts/smoke_all.py 80"

install:
	pip install -e ".[web]" pytest

# Launch OpenForge web UI (requires pip install -e ".[web]")
serve:
	$(PYTHON) -m openanalog serve --host $(HOST) --port $(PORT)

serve-wsl:
	$(WSL) "cd '$(WSL_ROOT)' && source .venv_wsl/bin/activate && pip install -e '.[web]' -q && python -m openanalog serve --host $(HOST) --port $(PORT)"
