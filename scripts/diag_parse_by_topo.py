#!/usr/bin/env python3
"""Diagnostic: parse failures by topology."""
import json
import os
import random
import subprocess
import tempfile
from collections import Counter

from openanalog.config import resolve_ngspice_cmd

ng = resolve_ngspice_cmd()
winners = [json.loads(l) for l in open("data/training/finetune.jsonl")]
random.seed(42)
sample = random.sample(winners, 20)

fail_by_topo: Counter = Counter()
ok_by_topo: Counter = Counter()
reasons: Counter = Counter()

for ex in sample:
    netlist = ex["messages"][2]["content"]
    topo = ex["messages"][1]["content"].split("Design a ")[1].split(" circuit")[0]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".sp", delete=False) as f:
        f.write(netlist)
        tmp = f.name
    r = subprocess.run([*ng, "-b", tmp], capture_output=True, text=True, timeout=10)
    os.unlink(tmp)
    err = (r.stderr or "").lower()
    if "syntax error" in err:
        reasons["syntax error"] += 1
        fail_by_topo[topo] += 1
    elif "undefined node" in err:
        reasons["undefined node"] += 1
        fail_by_topo[topo] += 1
    elif "unable to find definition of model" in err:
        reasons["missing model"] += 1
        fail_by_topo[topo] += 1
    elif "error" in err and r.returncode != 0:
        reasons["other error"] += 1
        fail_by_topo[topo] += 1
    else:
        ok_by_topo[topo] += 1

print("OK:", dict(ok_by_topo))
print("FAIL:", dict(fail_by_topo))
print("Reasons:", dict(reasons))
