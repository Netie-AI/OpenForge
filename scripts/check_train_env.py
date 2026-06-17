#!/usr/bin/env python3
"""CHECK 0: Fast training environment gate — no model download."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.train_env import (  # noqa: E402
    MIN_VRAM_GB_7B_4BIT,
    finetune_data_path,
    print_train_env,
    require_train_deps,
)


def main() -> None:
    require_train_deps()
    env = print_train_env()

    errors: list[str] = []

    if not env.get("cuda"):
        errors.append("CUDA not available — training requires GPU")

    vram = env.get("vram_gb", 0.0)
    if env.get("cuda") and vram < MIN_VRAM_GB_7B_4BIT:
        print(
            f"WARN: VRAM {vram:.1f}GB < {MIN_VRAM_GB_7B_4BIT}GB — "
            "dryrun will use 0.5B smoke model",
            flush=True,
        )

    data = finetune_data_path()
    if not data.exists():
        errors.append(f"Missing {data} — run scripts/build_training_jsonl.py")

    for pkg in ("datasets", "peft", "trl", "transformers", "bitsandbytes"):
        try:
            __import__(pkg)
        except ImportError:
            errors.append(f"Missing package: {pkg}")

    if errors:
        print("\nCHECK 0 FAILED:", flush=True)
        for e in errors:
            print(f"  - {e}", flush=True)
        print("\nFix: pip install -e '.[train]'", flush=True)
        sys.exit(1)

    print("\nCHECK 0 PASSED — training environment OK", flush=True)


if __name__ == "__main__":
    main()
