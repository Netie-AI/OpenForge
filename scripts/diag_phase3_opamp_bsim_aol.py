#!/usr/bin/env python3
"""Phase 3: diagnose opamp AOL on SKY130 BSIM4 — param sweep before full sizer."""
from __future__ import annotations

import os

os.environ["OPENFORGE_MODEL_SET"] = "sky130"
os.environ["OPENFORGE_SKY130_CARD"] = "bsim"

from openanalog.forge.spec_envelopes import DEV_MODE_SPECS
from openanalog.forge.topologies.opamp import OpAmpParams, OpAmpTopology
from openanalog.interface.designer import design
from openanalog.sim.models import set_active_model_set

RS321 = DEV_MODE_SPECS["opamp"]
AOL_FLOOR = 95.0 * 0.98  # min mode in spec


def show(label: str, p: OpAmpParams) -> None:
    topo = OpAmpTopology()
    m = topo.measure(p, with_full=False)
    v = m.values
    print(
        f"  {label}: AOL={v.get('aol_dB'):.1f} GBP={v.get('gbp_MHz'):.3f} "
        f"PM={v.get('pm_deg'):.1f} Iq={v.get('iq_uA'):.1f}uA "
        f"W6={p.W6:.1f} L6={p.L6:.1f} L1={p.L1:.1f} Cc={p.Cc*1e12:.2f}pF"
    )


def main() -> None:
    set_active_model_set("sky130")
    topo = OpAmpTopology()
    default = topo.default_params()

    print("=" * 70)
    print("1. DEFAULT on BSIM4")
    print("=" * 70)
    show("default", default)

    print("\n" + "=" * 70)
    print("2. SMOKE winner params (seed=42 budget=200 from sky130_bsim_smoke)")
    print("=" * 70)
    smoke = OpAmpParams(
        W1=2.002, L1=0.5, W3=1.963, L3=1.0, W5=2.347, L5=1.0,
        W6=80.25, L6=2.719, W7=74.28, L7=1.0, Wb=10.03, Lb=1.0,
        Iref=5.869e-6, Cc=0.0,
    )
    show("smoke", smoke)

    print("\n" + "=" * 70)
    print("3. L6 sweep (longer 2nd stage → higher ro → higher AOL)")
    print("=" * 70)
    for L6 in (1.0, 2.0, 3.0, 4.0, 6.0, 8.0):
        p = OpAmpParams(**{**smoke.as_dict(), "L6": L6})
        show(f"L6={L6}", p)

    print("\n" + "=" * 70)
    print("4. L1 sweep on smoke base")
    print("=" * 70)
    for L1 in (0.5, 1.0, 2.0, 3.0, 4.0):
        p = OpAmpParams(**{**smoke.as_dict(), "L1": L1, "L6": 4.0})
        show(f"L1={L1}", p)

    print("\n" + "=" * 70)
    print("5. Bundled-sized params re-measured on BSIM (Phase 1d seed=42)")
    print("=" * 70)
    bundled = OpAmpParams(
        W1=2.45, L1=0.5, W3=2.0, L3=1.0, W5=4.0, L5=1.0,
        W6=80.0, L6=2.0, W7=20.0, L7=1.0, Wb=4.0, Lb=1.0,
        Iref=8e-6, Cc=0.0,
    )
    show("bundled-ish", bundled)

    print("\n" + "=" * 70)
    print("6. SIZER runs (budget=250 seed=42)")
    print("=" * 70)
    for budget in (200, 250, 400):
        r = design(inline_spec=RS321, budget=budget, seed=42, record_kg=False)
        m = r["metrics"]
        print(
            f"  budget={budget} meets_all={r['meets_all']} "
            f"AOL={m.get('aol_dB'):.1f} GBP={m.get('gbp_MHz'):.3f} "
            f"PM={m.get('pm_deg'):.1f} Cc={r['params'].get('Cc')}"
        )


if __name__ == "__main__":
    main()
