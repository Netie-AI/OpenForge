#!/usr/bin/env python3
import json
import sys

winners = [json.loads(l) for l in sys.stdin]
bad = 0
for w in winners:
    nl = w.get("netlist", "")
    specs = w.get("measured_specs", w.get("sim_result", {}))
    if w.get("fitness") != 1:
        bad += 1
        continue
    if len(nl) < 200:
        bad += 1
        continue
    if any(v is None for v in specs.values()):
        bad += 1
print(f"checked {len(winners)} winners, quality failures: {bad}")
