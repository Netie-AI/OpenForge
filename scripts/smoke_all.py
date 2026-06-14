#!/usr/bin/env python3
"""
End-to-end smoke: one design per category via ngspice.
Exit 0 only if every *dev-mode* category returns meets_all=True.

vref is excluded — real bandgap needs SKY130 parasitic BJTs (Phase 3).
"""
from __future__ import annotations

import sys

from openanalog.interface.designer import design

# Categories achievable on bundled level-1 models (see AGENT_PLAN.md Phase 1)
SPECS = {
    "opamp": "gbp=1MHz pm>45 aol>90dB iq<200uA slew>0.1",
    "comparator": "type=comparator tp<10us vos<5mV iq<200uA",
    "switch": "type=switch ron<2000ohm bw>5MHz iq<10uA",
    "charge_pump": "type=charge_pump vout=4V ripple<50mV settle<10ms",
}

DEFERRED = ["vref"]  # Phase 3 — SKY130 bandgap with parasitic BJTs

BUDGET = int(sys.argv[1]) if len(sys.argv) > 1 else 80

if DEFERRED:
    print(f"SKIP (Phase 3): {', '.join(DEFERRED)}")

failed: list[str] = []
for cat, spec in SPECS.items():
    print(f"\n{'='*60}\nSMOKE {cat}  budget={BUDGET}\n{'='*60}")
    try:
        result = design(inline_spec=spec, budget=BUDGET, record_kg=False, seed=42)
    except Exception as e:
        print(f"FAIL {cat}: {e}")
        failed.append(cat)
        continue
    ok = result["meets_all"]
    metrics = result["metrics"]
    print(f"meets_all={ok}  score={result['score']}")
    print(f"metrics: {metrics}")
    print(f"compliance: { {k: v['pass'] for k,v in result['compliance'].items()} }")
    if not ok:
        failed.append(cat)

if failed:
    print(f"\nSMOKE FAILED: {failed}")
    sys.exit(1)
print(f"\nSMOKE OK — {len(SPECS)} dev-mode categories fitness=1")
