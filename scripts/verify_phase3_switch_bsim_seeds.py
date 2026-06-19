#!/usr/bin/env python3
"""Phase 3: switch Ron seed sensitivity on real SKY130 BSIM4 models."""
from __future__ import annotations

import os

os.environ["OPENFORGE_MODEL_SET"] = "sky130"
os.environ["OPENFORGE_SKY130_CARD"] = "bsim"

from openanalog.forge.spec_envelopes import DEV_MODE_SPECS
from openanalog.interface.designer import design
from openanalog.sim.models import set_active_model_set

RS2105 = DEV_MODE_SPECS["switch"]
SEEDS = [1, 3, 7, 11, 12]
BUDGET = 150  # matches BSIM smoke_all.py CATEGORY_BUDGET for switch


def main() -> None:
    set_active_model_set("sky130")
    print("=" * 70)
    print("Phase 3 — switch Ron seed sensitivity (SKY130 BSIM4, budget=150)")
    print("=" * 70)
    pass_n = 0
    for seed in SEEDS:
        r = design(inline_spec=RS2105, budget=BUDGET, seed=seed, record_kg=False)
        ok = r["meets_all"]
        pass_n += int(ok)
        m = r["metrics"]
        comp = r["compliance"]
        ron_pass = comp.get("ron_ohm", {}).get("pass", False)
        print(
            f"  seed={seed:2d} meets_all={ok} ron={m.get('ron_ohm'):.2f}Ω "
            f"(pass={ron_pass}) bw={m.get('bw_MHz'):.1f} "
            f"ton={m.get('ton_ns'):.2f} toff={m.get('toff_ns'):.2f}"
        )
        if not ok:
            fails = [k for k, v in comp.items() if not v.get("pass")]
            print(f"         fails: {fails}")
    print(f"\n  Pass rate: {pass_n}/{len(SEEDS)}")
    print(f"  Ron bar: <50 Ω (RS2105)")


if __name__ == "__main__":
    main()
