#!/usr/bin/env python3
"""Analyze opamp losers from forge diagnostic."""
import json
import sys
from collections import Counter

losers = []
for line in sys.stdin:
    rec = json.loads(line)
    if rec.get("topology") == "opamp":
        losers.append(rec)

print(f"Opamp losers: {len(losers)}")
fail_counts: Counter[str] = Counter()
for w in losers:
    compliance = w.get("compliance", {})
    for k, v in compliance.items():
        if v is False:
            fail_counts[k] += 1
print("Failing specs (most common first):")
for spec, n in fail_counts.most_common():
    print(f"  {spec}: {n}/{len(losers)}")
