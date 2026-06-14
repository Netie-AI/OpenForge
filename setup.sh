#!/bin/bash
set -e
echo "=== OpenAnalog Environment Setup ==="

if grep -qi microsoft /proc/version 2>/dev/null; then
    echo "[WSL detected] Configuring for WSL2..."
    IS_WSL=true
else
    echo "[Linux/macOS detected]"
    IS_WSL=false
fi

if command -v apt-get >/dev/null 2>&1; then
    export DEBIAN_FRONTEND=noninteractive
    SUDO="sudo"
    if [ "$(id -u)" = "0" ]; then
        SUDO=""
    fi
    $SUDO apt-get update -qq
    # Ubuntu 24.04+ uses libgl1; older scripts often reference libgl1-mesa-glx.
    $SUDO apt-get install -y ngspice git python3-pip python3-venv \
        poppler-utils tesseract-ocr libgl1 curl wget unzip || true
fi

python3 -m venv .venv_wsl
# shellcheck disable=SC1091
source .venv_wsl/bin/activate

pip install --upgrade pip
# Phase 1 (master plan): keep setup lightweight and reproducible.
# Heavy deps (torch/transformers/ultralytics) can be installed later as needed.
pip install -e "."

# Optional extras:
#   pip install -e ".[ingest]"   # marker-pdf
#   pip install -e ".[forge]"    # PySpice helpers
#   pip install -e ".[train]"    # torch/transformers/peft/datasets

pip install sky130 2>/dev/null || true
python -c "import sky130; sky130.setup()" 2>/dev/null || true

mkdir -p data/seeds papers/inbox
if [ ! -d "data/seeds/Masala-CHAI" ]; then
    git clone --depth=1 https://github.com/jitendra-bhandari/Masala-CHAI data/seeds/Masala-CHAI || true
fi
if [ ! -d "data/seeds/spice-datasets" ] && [ ! -d "spice-datasets" ]; then
    git clone --depth=1 https://github.com/symbench/spice-datasets data/seeds/spice-datasets || true
fi

if [ "$IS_WSL" = true ]; then
    echo 'export NGSPICE_PATH=$(which ngspice 2>/dev/null)' >> .venv_wsl/bin/activate
fi

if [ ! -f .env ]; then
    if [ -f env.local ]; then
        grep -E '^(ANTHROPIC|OPENAI|NEO4J)' env.local > .env 2>/dev/null || true
    fi
    cat >> .env << 'EOF'
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=openanalog
NGSPICE_TIMEOUT=30
SIM_WORKERS=4
EOF
fi

echo ""
echo "=== Setup complete ==="
echo "Activate (WSL): source .venv_wsl/bin/activate"
echo "Activate (Windows): .venv\\Scripts\\activate"
echo "Run: python -m openanalog --help"
