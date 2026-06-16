#!/usr/bin/env python3
"""Validate finetune.jsonl structure before Lambda upload."""
import json
import sys
from pathlib import Path

path = Path("data/training/finetune.jsonl")
if not path.exists():
    print(f"MISSING {path} — run scripts/build_training_jsonl.py first")
    sys.exit(1)

lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
print(f"Total examples: {len(lines)}")

sample = json.loads(lines[0])
print("Keys:", list(sample.keys()))
print("Message roles:", [m["role"] for m in sample["messages"]])
print("Netlist preview:", sample["messages"][2]["content"][:150])

empty = [
    i
    for i, line in enumerate(lines)
    if not json.loads(line)["messages"][2]["content"].strip()
]
print(f"Empty completions: {len(empty)} (must be 0)")

by_topo = {}
for line in lines:
    user = json.loads(line)["messages"][1]["content"]
    topo = user.split("Design a ", 1)[1].split(" circuit", 1)[0]
    by_topo[topo] = by_topo.get(topo, 0) + 1
print("By topology:", dict(sorted(by_topo.items())))

if empty:
    sys.exit(1)
