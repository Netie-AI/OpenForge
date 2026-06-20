#!/usr/bin/env python3
"""PVT/testbench - CMRR at 100 Hz (opamp only). Not yet in DEV_MODE_SPECS fitness gate."""
from __future__ import annotations

from openanalog.forge.spec_envelopes import DEV_MODE_SPECS
from openanalog.forge.topologies.opamp import OpAmpTopology
from openanalog.interface.designer import design

# Datasheet reference target (informative - not fitness gate until envelope updated)
RS321_CMRR_DB = 80.0


def _fmt_cmrr(val: float | None) -> str:
    if val is None:
        return "n/a"
    return f"{val:.1f} dB"


def main() -> int:
    topo = OpAmpTopology()
    default = topo.measure(topo.default_params(), with_full=True)
    print("=== opamp (bundled) ===")
    print(f"  defaults cmrr_dB={_fmt_cmrr(default.values.get('cmrr_dB'))}  (RS321 typ {RS321_CMRR_DB:.0f} dB)")
    r = design(inline_spec=DEV_MODE_SPECS["opamp"], budget=250, seed=42, record_kg=False)
    cmrr = r["metrics"].get("cmrr_dB")
    print(f"  sized s42  cmrr_dB={_fmt_cmrr(cmrr)}  meets_all={r['meets_all']}")
    if cmrr is None:
        print("  FAIL: cmrr_dB not measured")
        return 1
    print("\nNote: CMRR reported but not in DEV_MODE_SPECS - bench-only until envelope gate added.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
