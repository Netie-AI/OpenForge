#!/usr/bin/env python3
"""
End-to-end smoke: one design per category via ngspice.
Exit 0 only if every *dev-mode* category returns meets_all=True.

vref is excluded — real bandgap needs SKY130 parasitic BJTs (Phase 3).
"""
from __future__ import annotations

import sys

from openanalog.forge.spec_envelopes import DEFERRED_CATEGORIES, DEV_MODE_SPECS
from openanalog.interface.designer import design

# RS-series datasheet envelopes — the real fitness bar (see spec_envelopes.py)
SPECS = dict(DEV_MODE_SPECS)
DEFERRED = list(DEFERRED_CATEGORIES)

BUDGET = int(sys.argv[1]) if len(sys.argv) > 1 else 80

# Per-category sizing budgets (opamp needs more trials for AOL variance).
CATEGORY_BUDGET: dict[str, int] = {
    "opamp": max(BUDGET, 200),
    "comparator": max(BUDGET, 200),
    "switch": max(BUDGET, 150),
    "charge_pump": max(BUDGET, 120),
    "ldo": max(BUDGET, 180),
}
CATEGORY_SEED: dict[str, int] = {
    "opamp": 42,
    "comparator": 7,
    "switch": 11,
    "charge_pump": 19,
    "ldo": 23,
}

if DEFERRED:
    print(f"SKIP (Phase 3): {', '.join(DEFERRED)}")

failed: list[str] = []
for cat, spec in SPECS.items():
    cat_budget = CATEGORY_BUDGET.get(cat, BUDGET)
    cat_seed = CATEGORY_SEED.get(cat, 42)
    print(f"\n{'='*60}\nSMOKE {cat}  budget={cat_budget} seed={cat_seed}\n{'='*60}")
    try:
        result = design(inline_spec=spec, budget=cat_budget, record_kg=False, seed=cat_seed)
    except Exception as e:
        print(f"FAIL {cat}: {e}")
        failed.append(cat)
        continue
    ok = result["meets_all"]
    metrics = result["metrics"]
    print(f"meets_all={ok}  score={result['score']}")
    print(f"params: {result['params']}")
    print(f"metrics: {metrics}")
    print(f"compliance: { {k: v['pass'] for k,v in result['compliance'].items()} }")
    if not ok:
        failed.append(cat)

if failed:
    print(f"\nSMOKE FAILED: {failed}")
    sys.exit(1)
print(f"\nSMOKE OK — {len(SPECS)} dev-mode categories pass RS-series datasheet bar")
