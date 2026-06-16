#!/usr/bin/env python3
import json
import sys
from collections import Counter

winners = [json.loads(l) for l in sys.stdin]
reasons = Counter()
for w in winners:
    nl = w.get("netlist", "")
    specs = w.get("measured_specs", w.get("sim_result", {}))
    if w.get("fitness") != 1:
        reasons["fitness!=1"] += 1
        continue
    if len(nl) < 200:
        reasons["netlist<200"] += 1
        continue
    none_keys = [k for k, v in specs.items() if v is None]
    if none_keys:
        reasons[f"none:{','.join(none_keys[:2])}"] += 1
for r, n in reasons.most_common(10):
    print(f"  {r}: {n}")
