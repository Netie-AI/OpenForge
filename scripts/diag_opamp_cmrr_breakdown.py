#!/usr/bin/env python3
"""Diagnose opamp CMRR: tail Ro / mirror load vs measured CMRR (parallel to PSRR W3 sweep)."""
from __future__ import annotations

import argparse
import os

from openanalog.forge.sizer import size
from openanalog.forge.spec_envelopes import DEV_MODE_SPECS
from openanalog.forge.topologies.base import grab_meas, run_ngspice
from openanalog.forge.topologies.opamp import (
    OpAmpParams,
    OpAmpTopology,
    _build_ac_deck,
    _build_cmrr_deck,
)
from openanalog.interface.datasheet import parse_inline_spec
from openanalog.sim.models import resolve_models


def _model_label() -> str:
    rm = resolve_models()
    if rm.model_set == "sky130":
        card = os.getenv("OPENFORGE_SKY130_CARD", "level1")
        return f"sky130/{card}"
    return rm.model_set


def _cmrr_with_fixture(p: OpAmpParams, *, rl_ohm: float | None) -> float | None:
    """CMRR with optional RL fixture; same normalization as OpAmpTopology.measure()."""
    ok_aol, out_aol = run_ngspice(_build_ac_deck(p, 5.0, 10e-12), timeout=15)
    if not ok_aol:
        return None
    aol_100 = grab_meas("aol_db_100", out_aol)
    ok_cm, raw_cm = run_ngspice(
        _build_cmrr_deck(p, 5.0, 10e-12, rl_to_vcm_ohm=rl_ohm), timeout=15
    )
    if not ok_cm or aol_100 is None:
        return None
    acm_db = grab_meas("acm_db", raw_cm)
    if acm_db is None:
        return None
    cmrr = aol_100 - (acm_db + 20.0)
    return cmrr if cmrr >= 0 else None


def _row(label: str, p: OpAmpParams, topo: OpAmpTopology) -> None:
    m = topo.measure(p, with_full=True)
    cmrr = m.values.get("cmrr_dB")
    psrr = m.values.get("psrr_dB")
    aol = m.values.get("aol_dB")
    cmrr_rl = _cmrr_with_fixture(p, rl_ohm=10_000.0)
    cmrr_s = f"{cmrr:.1f}" if cmrr is not None else "n/a"
    psrr_s = f"{psrr:.1f}" if psrr is not None else "n/a"
    aol_s = f"{aol:.1f}" if aol is not None else "n/a"
    rl_s = f"{cmrr_rl:.1f}" if cmrr_rl is not None else "n/a"
    print(f"{label:14} cmrr={cmrr_s:>6} dB  rl10k={rl_s:>6} dB  psrr={psrr_s:>6} dB  aol={aol_s:>6} dB")


def main() -> int:
    parser = argparse.ArgumentParser(description="Opamp CMRR causal sweeps")
    parser.add_argument(
        "--lb-only",
        action="store_true",
        help="Run only M8 Lb sweep (BSIM follow-up)",
    )
    args = parser.parse_args()

    topo = OpAmpTopology()
    spec = parse_inline_spec(DEV_MODE_SPECS["opamp"])
    label = _model_label()
    print(f"RS321 CMRR typ=80 dB — tail Ro / mirror causal sweeps ({label} models)")
    print(f"{'case':14} {'cmrr':>12}  {'rl10k':>12}  {'psrr':>12}  {'aol':>10}")
    if args.lb_only:
        print("\n--- bias mirror M8 on nb: Lb sweep ---")
        for lb in (0.5, 1.0, 2.0, 4.0, 8.0):
            _row(f"Lb={lb:g}", OpAmpParams(Lb=lb), topo)
        return 0
    cases = [
        ("defaults", OpAmpParams()),
        ("Cc_10p", OpAmpParams(Cc=10e-12)),
        ("Cc_0.5p", OpAmpParams(Cc=0.5e-12)),
        ("Iref_5u", OpAmpParams(Iref=5e-6)),
        ("W3_30", OpAmpParams(W3=30.0)),
        ("W6_120", OpAmpParams(W6=120.0)),
    ]
    for label, p in cases:
        _row(label, p, topo)
    print("\n--- tail device M5: L5 sweep (Ro ∝ L/W) ---")
    for l5 in (0.5, 1.0, 2.0, 4.0, 8.0):
        _row(f"L5={l5:g}", OpAmpParams(L5=l5), topo)
    print("\n--- tail device M5: W5 sweep ---")
    for w5 in (4, 8, 16, 32, 64):
        _row(f"W5={w5}", OpAmpParams(W5=float(w5)), topo)
    print("\n--- bias mirror M8 on nb: Lb sweep ---")
    for lb in (0.5, 1.0, 2.0, 4.0, 8.0):
        _row(f"Lb={lb:g}", OpAmpParams(Lb=lb), topo)
    print("\n--- PMOS mirror load M3/M4: W3 sweep (PSRR precedent) ---")
    for w3 in (8, 30, 60, 100, 150):
        _row(f"W3={w3}", OpAmpParams(W3=float(w3)), topo)
    c = size(topo, spec, budget=250, seed=42)
    cmrr = c.metrics.values.get("cmrr_dB")
    psrr = c.metrics.values.get("psrr_dB")
    cmrr_s = f"{cmrr:.1f}" if cmrr is not None else "n/a"
    psrr_s = f"{psrr:.1f}" if psrr is not None else "n/a"
    print(f"\nsized s42      cmrr={cmrr_s} dB  psrr={psrr_s} dB  meets_all={c.meets_all}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
