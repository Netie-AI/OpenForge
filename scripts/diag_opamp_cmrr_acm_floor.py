#!/usr/bin/env python3
"""CMRR noise-floor check: raw ACM linear amplitude + CM stimulus at both inputs.

Claude reviewer gate (2026-06-20): before more sweep axes, confirm CM-AC output
is real signal rather than dB-of-near-zero division artifact.
"""
from __future__ import annotations

import os
import re

from openanalog.forge.topologies.base import grab_meas, run_ngspice
from openanalog.forge.topologies.opamp import (
    OpAmpParams,
    _build_ac_deck,
    _build_cmrr_deck,
)
from openanalog.sim.models import resolve_models


def _model_label() -> str:
    rm = resolve_models()
    if rm.model_set == "sky130":
        card = os.getenv("OPENFORGE_SKY130_CARD", "level1")
        return f"sky130/{card}"
    return rm.model_set


def _build_cmrr_probe_deck(p: OpAmpParams, supply_V: float, cload_F: float) -> str:
    """CM deck with linear ACM + input-node probes (stimulus sanity)."""
    base = _build_cmrr_deck(p, supply_V, cload_F, rl_to_vcm_ohm=None)
    extra = """
meas ac acm_vm find vm(vout) at=100
meas ac vinp_db find vdb(vinp) at=100
meas ac vinn_db find vdb(vinn) at=100
meas ac vinp_vm find vm(vinp) at=100
meas ac vinn_vm find vm(vinn) at=100
meas ac vinp_vp find vp(vinp) at=100
meas ac vinn_vp find vp(vinn) at=100
"""
    return base.replace("meas ac acm_db find vdb(vout) at=100\n", extra + "meas ac acm_db find vdb(vout) at=100\n")


def _harness_lines(deck: str) -> list[str]:
    keys = ("Vinp ", "Vinn ", "ac dec", "meas ac acm")
    return [ln.rstrip() for ln in deck.splitlines() if any(k in ln for k in keys)]


def _row(label: str, p: OpAmpParams) -> None:
    ok_ac, raw_ac = run_ngspice(_build_ac_deck(p, 5.0, 10e-12), timeout=15)
    ok_cm, raw_cm = run_ngspice(_build_cmrr_probe_deck(p, 5.0, 10e-12), timeout=15)
    if not ok_ac or not ok_cm:
        print(f"{label:8} FAIL ngspice")
        return

    aol_100 = grab_meas("aol_db_100", raw_ac)
    acm_db = grab_meas("acm_db", raw_cm)
    acm_vm = grab_meas("acm_vm", raw_cm)
    vinp_vm = grab_meas("vinp_vm", raw_cm)
    vinn_vm = grab_meas("vinn_vm", raw_cm)
    vinp_db = grab_meas("vinp_db", raw_cm)
    vinn_db = grab_meas("vinn_db", raw_cm)
    vinp_vp = grab_meas("vinp_vp", raw_cm)
    vinn_vp = grab_meas("vinn_vp", raw_cm)

    cmrr = None
    if aol_100 is not None and acm_db is not None:
        cmrr = aol_100 - (acm_db + 20.0)

    # Expected CM stimulus: ac 0.1 V peak on both inputs → vm ≈ 0.1 V, vdb ≈ -20 dB
    stim_ok = (
        vinp_vm is not None
        and vinn_vm is not None
        and abs(vinp_vm - 0.1) < 0.02
        and abs(vinn_vm - 0.1) < 0.02
        and abs(vinp_vm - vinn_vm) < 1e-6
    )
    phase_ok = vinp_vp is not None and vinn_vp is not None and abs(vinp_vp - vinn_vp) < 1.0

    floor_flag = ""
    if acm_vm is not None:
        if acm_vm < 1e-9:
            floor_flag = " **NOISE-FLOOR?**"
        elif acm_vm < 1e-6:
            floor_flag = " (very small)"

    cmrr_s = f"{cmrr:.1f}" if cmrr is not None else "n/a"
    print(
        f"{label:8} cmrr={cmrr_s:>6} dB  acm_vm={acm_vm:.3e} V  acm_db={acm_db:.1f} dB"
        f"  aol100={aol_100:.1f} dB  stim_ok={stim_ok} phase_ok={phase_ok}{floor_flag}"
    )
    print(
        f"         vinp vm={vinp_vm:.4f} V ({vinp_db:.1f} dB)  "
        f"vinn vm={vinn_vm:.4f} V ({vinn_db:.1f} dB)  "
        f"vp delta={abs(vinp_vp - vinn_vp):.2f} deg"
    )


def main() -> int:
    label = _model_label()
    print(f"CMRR ACM noise-floor probe ({label})")
    print("Harness excerpt (defaults):")
    for ln in _harness_lines(_build_cmrr_probe_deck(OpAmpParams(), 5.0, 10e-12)):
        print(f"  {ln}")
    print()
    print(f"{'case':8} {'cmrr':>8}  {'acm_vm':>12}  notes")
    for lb in (0.5, 1.0, 2.0, 4.0, 8.0):
        _row(f"Lb={lb:g}", OpAmpParams(Lb=lb))
    _row("default", OpAmpParams())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
