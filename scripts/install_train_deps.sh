#!/usr/bin/env bash
# Install train extras into WSL venv for pre-launch checks.
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv_wsl/bin/activate
pip install --upgrade pip
pip install -e ".[train]"
echo "Train deps installed."
