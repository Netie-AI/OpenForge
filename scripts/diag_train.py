#!/usr/bin/env python3
"""One-shot diagnostic: which python, import order, GPU."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

print(f"python: {sys.executable}", flush=True)
print(f"cwd:    {Path.cwd()}", flush=True)
print(f"repo:   {_ROOT}", flush=True)

venv_py = _ROOT / ".venv_train" / "Scripts" / "python.exe"
if sys.executable.lower() != str(venv_py).lower():
    print(f"WARN: not using venv python — expected {venv_py}", flush=True)
    print("Fix: .\\.venv_train\\Scripts\\python.exe -u scripts/dryrun_finetune.py", flush=True)

from scripts.train_env import print_train_env, require_train_deps  # noqa: E402

require_train_deps()
env = print_train_env()
print(f"cuda={env.get('cuda')} vram={env.get('vram_gb')} gpu={env.get('gpu')}", flush=True)
print("DIAG OK", flush=True)
