#!/usr/bin/env bash
# Phase 5 pre-launch hardening — run all checks locally (prefer CUDA).
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -f .venv_wsl/bin/activate ]; then
  # shellcheck disable=SC1091
  source .venv_wsl/bin/activate
fi

echo "=== ENV ==="
python - <<'PY'
import sys
try:
    import torch
    print(f"torch {torch.__version__}  CUDA={torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory/1e9:.1f} GB")
except ImportError:
    print("torch NOT installed")
    sys.exit(1)
PY

for pkg in transformers peft trl datasets bitsandbytes; do
  python -c "import $pkg; print('$pkg', getattr($pkg,'__version__','ok'))" 2>/dev/null || echo "MISSING: $pkg"
done

echo ""
echo "=== CHECK 1: Chat format ==="
python scripts/check_chat_format.py

echo ""
echo "=== CHECK 2: Netlist parse quality ==="
python scripts/check_netlist_parse.py

echo ""
echo "=== CHECK 4: LoRA target modules ==="
python scripts/check_lora_targets.py

echo ""
echo "=== CHECK 3: GPU dry-run (10 steps) ==="
python scripts/dryrun_finetune.py

echo ""
echo "=== ALL PRE-LAUNCH CHECKS COMPLETE ==="
