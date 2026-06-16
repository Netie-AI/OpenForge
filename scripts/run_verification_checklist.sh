#!/usr/bin/env bash
set -euo pipefail
cd /mnt/c/Users/oojia/OpenForge
source .venv_wsl/bin/activate

echo "=== BUNDLED SMOKE ==="
python scripts/smoke_all.py 80

echo "=== SKY130 SMOKE ==="
OPENFORGE_MODEL_SET=sky130 python scripts/smoke_all.py 80

echo "=== PYTEST ==="
python -m pytest tests/ -q

echo "=== FORGE 20 ==="
python -m openanalog forge --n 20 --reset 2>&1 | tail -5

echo "=== GIT LOG ==="
git log --oneline -5

echo "=== GIT STATUS ==="
git status --short

echo "=== SECRETS CHECK (staged) ==="
if git diff --cached | grep -iE 'key|token|secret|password'; then exit 1; else echo clean; fi

echo "=== SECRETS CHECK (unstaged) ==="
if git diff | grep -iE 'key|token|secret|password'; then exit 1; else echo clean; fi
