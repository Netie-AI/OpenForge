#!/usr/bin/env python3
import json
import sys
from pathlib import Path

p = Path("data/training/winners.jsonl")
if not p.exists():
    print("NO winners.jsonl")
    sys.exit(0)
lines = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
print(f"Total winners: {len(lines)}")
if lines:
    sample = lines[0]
    print(f"Keys: {list(sample.keys())}")
    print(f"Has measured_specs: {'measured_specs' in sample}")
    print(f"Has netlist: {'netlist' in sample and len(sample.get('netlist','')) > 0}")
    print(f"netlist_len: {len(sample.get('netlist') or sample.get('output') or '')}")
    print(f"Sample fitness: {sample.get('fitness')}")
    print(f"Sample topology: {sample.get('topology')}")
    print("First line:", json.dumps(sample)[:300])
