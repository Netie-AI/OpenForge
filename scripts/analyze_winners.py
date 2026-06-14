#!/usr/bin/env python3
import json
import statistics
import sys
from collections import Counter

winners = [json.loads(l) for l in sys.stdin]
counts = Counter(w["topology"] for w in winners)
print(f"Total: {len(winners)}")
for t, n in sorted(counts.items()):
    print(f"  {t}: {n}")
print()
opamp = [w for w in winners if w["topology"] == "opamp"]
if opamp:
    w1s = [w["params"].get("W1", 0) for w in opamp]
    irefs = [w["params"].get("Iref", 0) * 1e6 for w in opamp]
    print(f"opamp W1 range: {min(w1s):.2f}–{max(w1s):.2f}")
    print(f"opamp Iref range: {min(irefs):.3f}–{max(irefs):.3f} µA")
    if len(w1s) > 1:
        print(f"opamp W1 std: {statistics.stdev(w1s):.2f}")
