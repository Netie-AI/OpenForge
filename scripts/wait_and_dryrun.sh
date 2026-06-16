#!/usr/bin/env bash
# Wait for pip install to finish, then run CHECK 4 + CHECK 3 on CUDA.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "Waiting for pip install -e .[train] to finish..."
while pgrep -f 'pip install -e .\[train\]' >/dev/null 2>&1; do
  echo "$(date +%H:%M:%S) pip still installing..."
  sleep 30
done
echo "$(date +%H:%M:%S) pip done."

source .venv_wsl/bin/activate
python scripts/check_wsl_train_env.sh 2>/dev/null || true
python - <<'PY'
import torch, peft, trl, bitsandbytes, transformers
print("torch", torch.__version__, "cuda", torch.cuda.is_available())
if torch.cuda.is_available():
    print("gpu", torch.cuda.get_device_name(0))
PY

echo ""
echo "=== CHECK 4 ==="
python scripts/check_lora_targets.py

echo ""
echo "=== CHECK 3 (GPU dry-run, 10 steps) ==="
python scripts/dryrun_finetune.py

echo ""
echo "=== ALL REMAINING CHECKS COMPLETE ==="
