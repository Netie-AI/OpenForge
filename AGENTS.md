# AGENTS.md

## Cursor Cloud specific instructions

OpenAnalog (web UI brand: **OpenForge**) is a single Python product: an analog-IC
design pipeline (`PDF → schematic → SPICE → ngspice forge → training data`). It is
driven by one CLI (`python -m openanalog ...`) plus an optional FastAPI web UI. State
is file-based under `data/`; there is no database server, queue, or docker-compose.

### Environment (already provisioned by the update script / VM snapshot)
- Python virtualenv lives at `.venv` (activate with `source .venv/bin/activate`). The
  repo's `setup.sh` creates `.venv_wsl` instead — that path is for Windows/WSL; on this
  Linux VM use `.venv`.
- The update script installs the package editable with the `web` extra plus `pytest`
  (`pip install -e ".[web]" pytest`).
- **`ngspice` is a required system binary** (the core SPICE simulation engine), installed
  via `apt-get install -y ngspice` and baked into the VM snapshot — it is NOT a pip
  dependency, so the update script does not reinstall it. Verify with
  `curl -s localhost:8080/api/health` (reports `ngspice_available`) or `ngspice -v`.
- Optional extras are not installed by default: `.[ingest]` (marker-pdf, needs
  poppler/tesseract), `.[forge]` (PySpice), `.[train]` (torch/transformers, GPU). LLM API
  keys (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, etc.) are optional — the pipeline runs
  deterministically when LLM use is left off.

### Lint / test / run (standard commands live in the `Makefile`)
- Lint: `python -m compileall openanalog -q`.
- Tests: `python -m pytest tests/ -q`. Set `OPENFORGE_MODEL_SET=bundled` (as CI does) so
  tests use the bundled PDK rather than an external sky130 install. The suite takes
  ~2.5 min because the ngspice behavioral tests run real simulations.
- ngspice end-to-end smoke: `python scripts/smoke_all.py 80`.
- Web UI: `python -m openanalog serve --host 127.0.0.1 --port 8080`. There is no separate
  dev/prod mode — uvicorn is launched with `reload=False` hardcoded, so a code change
  requires restarting the server (no hot reload). Health: `GET /api/health`; design a
  chip via `POST /api/design` or the browser UI (select a preset, leave the LLM toggle
  off, click "Design Chip").
