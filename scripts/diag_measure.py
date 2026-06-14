#!/usr/bin/env python3
"""Diagnostic: measure default params for every topology via ngspice."""
from openanalog.forge.topologies import get_topology

for cat in ["vref", "comparator", "charge_pump", "switch", "opamp"]:
    t = get_topology(cat)
    p = t.default_params()
    m = t.measure(p, with_full=True)
    print(f"=== {cat} ok={m.ok}")
    print(f"values: {m.values}")
    if m.error:
        print(f"error: {m.error[:300]}")
    print()
