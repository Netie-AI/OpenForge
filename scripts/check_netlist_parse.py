#!/usr/bin/env python3
"""CHECK 2: Sample netlists from finetune.jsonl and ngspice syntax-check."""
from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import tempfile
from pathlib import Path

from openanalog.config import resolve_ngspice_cmd
from openanalog.forge.simulator import circuit_only_netlist

FINETUNE = Path("data/training/finetune.jsonl")
ERROR_KEYS = (
    "syntax error",
    "undefined node",
    "no such file",
    "fatal error",
    "unable to find definition of model",
)

ngspice = resolve_ngspice_cmd()
if not ngspice:
    print("WARN: ngspice not found — skipping parse check")
    sys.exit(0)

winners = []
with FINETUNE.open(encoding="utf-8") as f:
    for line in f:
        winners.append(json.loads(line))

random.seed(42)
sample = random.sample(winners, min(20, len(winners)))

parse_ok = 0
parse_fail = 0
fail_examples: list[tuple[str, str]] = []

for ex in sample:
    netlist = circuit_only_netlist(ex["messages"][2]["content"])
    topo = ex["messages"][1]["content"][:30]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".sp", delete=False) as fh:
        fh.write(netlist)
        tmp = fh.name

    try:
        result = subprocess.run(
            [*ngspice, "-b", tmp],
            capture_output=True,
            text=True,
            timeout=10,
        )
    finally:
        os.unlink(tmp)

    stderr = (result.stderr or "").lower()
    has_error = any(k in stderr for k in ERROR_KEYS)
    if has_error:
        parse_fail += 1
        fail_examples.append((topo[:40], stderr[:200]))
    else:
        parse_ok += 1

print(f"Sampled: {len(sample)}")
print(f"Parse OK:   {parse_ok}")
print(f"Parse FAIL: {parse_fail}")
if fail_examples:
    print("\nFailing examples:")
    for topo, err in fail_examples[:3]:
        print(f"  [{topo}] {err}")

if parse_fail > 2:
    print("\nSTOP: >2/20 netlists failed parse — rebuild with parse gate")
    sys.exit(1)
print("\nCHECK 2 PASSED")
