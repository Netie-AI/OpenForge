#!/usr/bin/env python3
"""Compare opamp CMRR bench with and without datasheet-style RL fixture."""
from __future__ import annotations

from openanalog.forge.spec_envelopes import DEV_MODE_SPECS
from openanalog.forge.topologies.base import grab_meas, run_ngspice
from openanalog.forge.topologies.opamp import OpAmpParams, OpAmpTopology, _build_cmrr_deck
from openanalog.interface.designer import design


def _measure_acm(p: OpAmpParams, *, rl_to_vcm_ohm: float | None) -> float | None:
    ok_cm, out_cm = run_ngspice(_build_cmrr_deck(p, 5.0, 10e-12, rl_to_vcm_ohm=rl_to_vcm_ohm), timeout=15)
    if not ok_cm:
        return None
    acm_db = grab_meas("acm_db", out_cm)
    return acm_db


def _fmt(v: float | None) -> str:
    return "n/a" if v is None else f"{v:.1f}"


def main() -> int:
    topo = OpAmpTopology()
    print("CMRR fixture sanity (RS321 header has RL=10k to VS/2)")
    default_p = OpAmpParams()
    cmrr_b = topo.measure(default_p, with_full=True).values.get("cmrr_dB")
    acm_b = _measure_acm(default_p, rl_to_vcm_ohm=None)
    acm_r = _measure_acm(default_p, rl_to_vcm_ohm=10_000.0)
    cmrr_r = None
    if cmrr_b is not None and acm_b is not None and acm_r is not None:
        cmrr_r = cmrr_b - (acm_r - acm_b)
    print(f"defaults base      acm={_fmt(acm_b)} dB  cmrr={_fmt(cmrr_b)} dB")
    print(f"defaults rl=10k    acm={_fmt(acm_r)} dB  cmrr={_fmt(cmrr_r)} dB")
    if cmrr_b is not None and cmrr_r is not None:
        print(f"defaults delta(rl-base)={cmrr_r - cmrr_b:+.2f} dB")

    r = design(inline_spec=DEV_MODE_SPECS["opamp"], budget=250, seed=42, record_kg=False)
    sized_p = OpAmpParams(**r["params"])
    cmrr_bs = r["metrics"].get("cmrr_dB")
    acm_bs = _measure_acm(sized_p, rl_to_vcm_ohm=None)
    acm_rs = _measure_acm(sized_p, rl_to_vcm_ohm=10_000.0)
    cmrr_rs = None
    if cmrr_bs is not None and acm_bs is not None and acm_rs is not None:
        cmrr_rs = cmrr_bs - (acm_rs - acm_bs)
    print(f"sized s42 base     acm={_fmt(acm_bs)} dB  cmrr={_fmt(cmrr_bs)} dB")
    print(f"sized s42 rl=10k   acm={_fmt(acm_rs)} dB  cmrr={_fmt(cmrr_rs)} dB")
    if cmrr_bs is not None and cmrr_rs is not None:
        print(f"sized delta(rl-base)={cmrr_rs - cmrr_bs:+.2f} dB")

    if any(v is None for v in (cmrr_b, cmrr_r, cmrr_bs, cmrr_rs)):
        print("FAIL: fixture comparison missing one or more measurements")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
