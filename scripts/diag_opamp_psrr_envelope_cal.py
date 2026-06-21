#!/usr/bin/env python3
"""Single-category PSRR envelope calibration — before DEV_MODE_SPECS / Phase 1d change.

Runs RS321 base spec with optional psrr>XdB appended; does NOT modify spec_envelopes.py.
See docs/semicon-log.md entry 5 (W3 causal knob; sizer W3 cap vs manual W3=150 sweep).
"""
from __future__ import annotations

import argparse

from openanalog.forge.sizer import size
from openanalog.forge.spec_envelopes import DEV_MODE_SPECS
from openanalog.forge.topologies.opamp import OpAmpParams, OpAmpTopology
from openanalog.interface.datasheet import parse_inline_spec

BASE = DEV_MODE_SPECS["opamp"]
DEFAULT_SEEDS = (42, 1, 7, 99)
BUDGET = 250


def _run_case(label: str, inline: str, seeds: tuple[int, ...]) -> None:
    spec = parse_inline_spec(inline)
    psrr_tgt = spec["targets"].get("psrr_dB")
    psrr_note = f" (+psrr>{psrr_tgt['value']:.0f}dB)" if psrr_tgt else ""
    print(f"\n=== {label} ({inline.strip()}{psrr_note}) ===")
    topo = OpAmpTopology()
    w3_lo, w3_hi, _ = topo.param_ranges()["W3"]
    print(f"  sizer W3 range: {w3_lo:.0f}–{w3_hi:.0f} µm (manual sweep used W3=150 µm)")
    for seed in seeds:
        c = size(topo, spec, budget=BUDGET, seed=seed)
        psrr = c.metrics.values.get("psrr_dB")
        w3 = c.params.W3 if hasattr(c.params, "W3") else None
        psrr_s = f"{psrr:.1f}" if psrr is not None else "n/a"
        w3_s = f"{w3:.1f}" if w3 is not None else "n/a"
        print(
            f"  seed={seed:3}  psrr={psrr_s:>6} dB  W3={w3_s:>6} µm  "
            f"meets_all={c.meets_all}  aol={c.metrics.values.get('aol_dB', 'n/a')}"
        )


def main() -> int:
    ap = argparse.ArgumentParser(description="PSRR envelope calibration (opamp only, no gate change)")
    ap.add_argument("--psrr-db", type=float, default=85.0, help="PSRR min target to append (default 85)")
    ap.add_argument("--seeds", type=int, nargs="+", default=list(DEFAULT_SEEDS))
    args = ap.parse_args()
    seeds = tuple(args.seeds)
    psrr_spec = f"{BASE} psrr>{args.psrr_db:.0f}dB"

    print("RS321 PSRR envelope calibration (bench-only — DEV_MODE_SPECS unchanged)")
    print(f"Base spec: {BASE}")
    _run_case("baseline (no PSRR in spec)", BASE, seeds)
    _run_case(f"calibration (+psrr>{args.psrr_db:.0f}dB)", psrr_spec, seeds)

    topo = OpAmpTopology()
    m = topo.measure(OpAmpParams(W3=150.0), with_full=True)
    psrr = m.values.get("psrr_dB")
    print(f"\n=== manual W3=150 µm (outside sizer range) ===")
    print(f"  psrr={psrr:.1f} dB  (semicon-log entry 5: ~83 dB at W3=150)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
