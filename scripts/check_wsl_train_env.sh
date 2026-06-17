#!/usr/bin/env bash
cd "$(dirname "$0")/.."
source .venv_wsl/bin/activate
python - <<'PY'
import sys
for pkg in ("torch", "peft", "trl", "bitsandbytes", "transformers"):
    try:
        m = __import__(pkg)
        print(pkg, getattr(m, "__version__", "ok"))
    except ImportError as e:
        print(pkg, "MISSING", e)
        sys.exit(1)
import torch
print("cuda", torch.cuda.is_available())
if torch.cuda.is_available():
    print("gpu", torch.cuda.get_device_name(0))
PY
