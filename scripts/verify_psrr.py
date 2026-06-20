#!/usr/bin/env python3
"""PVT/testbench — PSRR at 100 Hz (opamp, LDO, vref). Not yet in DEV_MODE_SPECS fitness gate."""
from __future__ import annotations

import os
import sys

from openanalog.forge.spec_envelopes import DEV_MODE_SPECS
from openanalog.forge.topologies.ldo import LDOParams, LDOTopology
from openanalog.forge.topologies.opamp import OpAmpParams, OpAmpTopology
from openanalog.forge.topologies.vref import VRefParams, VRefTopology
from openanalog.interface.designer import design
from openanalog.sim.models import set_active_model_set

# Datasheet reference targets (informative — not fitness gate until envelope updated)
RS321_PSRR_DB = 85.0
RS3001_PSRR_DB = 60.0  # typical LDO PSRR floor for bench sanity


def _fmt_psrr(val: float | None) -> str:
    if val is None:
        return "n/a"
    return f"{val:.1f} dB"


def _run_opamp() -> int:
    topo = OpAmpTopology()
    default = topo.measure(topo.default_params(), with_full=True)
    print("=== opamp (bundled) ===")
    print(f"  defaults psrr_dB={_fmt_psrr(default.values.get('psrr_dB'))}  (RS321 typ {RS321_PSRR_DB:.0f} dB)")
    r = design(inline_spec=DEV_MODE_SPECS["opamp"], budget=250, seed=42, record_kg=False)
    psrr = r["metrics"].get("psrr_dB")
    print(f"  sized s42  psrr_dB={_fmt_psrr(psrr)}  meets_all={r['meets_all']}")
    if psrr is None:
        print("  FAIL: psrr_dB not measured")
        return 1
    return 0


def _run_ldo() -> int:
    topo = LDOTopology()
    default = topo.measure(LDOParams(), with_full=True)
    print("=== ldo (bundled) ===")
    print(f"  defaults psrr_dB={_fmt_psrr(default.values.get('psrr_dB'))}  (informative floor ~{RS3001_PSRR_DB:.0f} dB)")
    r = design(inline_spec=DEV_MODE_SPECS["ldo"], budget=200, seed=7, record_kg=False)
    psrr = r["metrics"].get("psrr_dB")
    print(f"  sized s7   psrr_dB={_fmt_psrr(psrr)}  meets_all={r['meets_all']}")
    if psrr is None:
        print("  FAIL: psrr_dB not measured")
        return 1
    return 0


def _run_vref() -> int:
    os.environ.setdefault("OPENFORGE_MODEL_SET", "sky130")
    set_active_model_set("sky130")
    topo = VRefTopology()
    default = topo.measure(VRefParams(), with_full=True)
    print("=== vref (SKY130 placeholder BJTs) ===")
    print(f"  defaults psrr_dB={_fmt_psrr(default.values.get('psrr_dB'))}  line_reg_mV={default.values.get('line_reg_mV')}")
    if default.values.get("psrr_dB") is None:
        print("  FAIL: psrr_dB not measured")
        return 1
    return 0


def main() -> int:
    rc = 0
    rc |= _run_opamp()
    rc |= _run_ldo()
    rc |= _run_vref()
    print("\nNote: PSRR reported but not in DEV_MODE_SPECS — bench-only until envelope gate added.")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
