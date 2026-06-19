#!/usr/bin/env python3
"""Phase 3: opamp AOL seed sensitivity on real SKY130 BSIM4 models."""
from __future__ import annotations

import os

os.environ["OPENFORGE_MODEL_SET"] = "sky130"
os.environ["OPENFORGE_SKY130_CARD"] = "bsim"

from openanalog.forge.spec_envelopes import DEV_MODE_SPECS
from openanalog.interface.designer import design
from openanalog.sim.models import set_active_model_set

RS321 = DEV_MODE_SPECS["opamp"]
SEEDS = [1, 3, 7, 42, 99]
BUDGET = 200


def main() -> None:
    set_active_model_set("sky130")
    print("=" * 70)
    print("Phase 3 — opamp seed sensitivity (SKY130 BSIM4, budget=200)")
    print("=" * 70)
    pass_n = 0
    for seed in SEEDS:
        r = design(inline_spec=RS321, budget=BUDGET, seed=seed, record_kg=False)
        ok = r["meets_all"]
        pass_n += int(ok)
        m = r["metrics"]
        fail = [k for k, v in r["compliance"].items() if v.get("pass") is False]
        p = r["params"]
        print(
            f"  seed={seed:2d} meets_all={ok} AOL={m.get('aol_dB'):.1f} "
            f"GBP={m.get('gbp_MHz'):.3f} PM={m.get('pm_deg'):.1f} "
            f"L1={p.get('L1'):.2f} fail={fail or '-'}"
        )
    print(f"\n  Pass rate: {pass_n}/{len(SEEDS)}")


if __name__ == "__main__":
    main()
