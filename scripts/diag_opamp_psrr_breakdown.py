#!/usr/bin/env python3
"""Diagnose opamp PSRR: closable by sizing or structural floor?"""
from __future__ import annotations

from openanalog.forge.sizer import size
from openanalog.forge.spec_envelopes import DEV_MODE_SPECS
from openanalog.forge.topologies.opamp import OpAmpParams, OpAmpTopology
from openanalog.interface.datasheet import parse_inline_spec


def main() -> int:
    topo = OpAmpTopology()
    spec = parse_inline_spec(DEV_MODE_SPECS["opamp"])
    cases = [
        ("defaults", OpAmpParams()),
        ("Cc_10p", OpAmpParams(Cc=10e-12)),
        ("Cc_0.5p", OpAmpParams(Cc=0.5e-12)),
        ("Iref_5u", OpAmpParams(Iref=5e-6)),
        ("W3_30", OpAmpParams(W3=30.0)),
        ("W6_120", OpAmpParams(W6=120.0)),
    ]
    print(f"RS321 PSRR typ=85 dB")
    for label, p in cases:
        m = topo.measure(p, with_full=True)
        psrr = m.values.get("psrr_dB")
        aol = m.values.get("aol_dB")
        print(f"{label:12} psrr={psrr:.1f} dB  aol={aol:.1f} dB" if psrr else f"{label:12} psrr=n/a")
    for w3 in (8, 30, 60, 100, 150):
        m = topo.measure(OpAmpParams(W3=float(w3)), with_full=True)
        psrr = m.values.get("psrr_dB")
        print(f"W3={w3:3} psrr={psrr:.1f} dB" if psrr else f"W3={w3:3} psrr=n/a")
    c = size(topo, spec, budget=250, seed=42)
    psrr = c.metrics.values.get("psrr_dB")
    print(f"sized s42    psrr={psrr:.1f} dB  meets_all={c.meets_all}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
