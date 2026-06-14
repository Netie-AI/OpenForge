from __future__ import annotations

import json
from pathlib import Path

from openanalog.config import TRAINING_DIR, ensure_dirs


def build_alpaca_dataset(
    winners_path: Path | None = None,
    out_path: Path | None = None,
) -> Path:
    ensure_dirs()
    src = winners_path or TRAINING_DIR / "winners.jsonl"
    out = out_path or TRAINING_DIR / "alpaca_train.json"
    records = []
    if src.exists():
        for line in src.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            records.append(
                {
                    "instruction": r.get("instruction", ""),
                    "input": r.get("input", ""),
                    "output": r.get("output", ""),
                }
            )
    out.write_text(json.dumps(records, indent=2), encoding="utf-8")
    return out
