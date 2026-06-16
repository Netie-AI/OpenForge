#!/usr/bin/env bash
# One-command launcher for the OpenForge web UI (WSL).
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -f .venv_wsl/bin/activate ]]; then
  source .venv_wsl/bin/activate
elif [[ -f .venv/bin/activate ]]; then
  source .venv/bin/activate
else
  echo "No venv found — run: pip install -e '.[web]'" >&2
  exit 1
fi
pip install -e ".[web]" -q
HOST="${OPENFORGE_HOST:-127.0.0.1}"
PORT="${OPENFORGE_PORT:-8080}"
echo "OpenForge → http://${HOST}:${PORT}"
exec python -m openanalog serve --host "$HOST" --port "$PORT"
