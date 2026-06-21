#!/usr/bin/env python3
"""Deep BJT model sanity — connection styles and Vbe/ΔVbe."""
from __future__ import annotations

import os

from openanalog.forge.topologies.base import run_ngspice
from openanalog.sim.models import resolve_models, set_active_model_set


def run(label: str, body: str) -> None:
    ms = resolve_models()
    deck = ms.block + body
    ok, out = run_ngspice(deck, timeout=25)
    print(f"\n=== {label} ok={ok} ===")
    for line in out.splitlines():
        lo = line.lower()
        if "error" in lo or "v(" in lo or "i(" in lo or "warning" in lo:
            if "rusage" not in lo:
                print(line.rstrip())


def main() -> None:
    os.environ.setdefault("OPENFORGE_MODEL_SET", "sky130")
    set_active_model_set("sky130")
    ms = resolve_models()
    npn = ms.npn

    # Diode-connected: C=B, E=0, substrate=0 vs substrate=VCC
    run(
        "diode sub=0",
        f"""
Vcc vcc 0 5
Q1 vcc vcc 0 0 {npn} area=1
Ib vcc vcc 1u
.control
op
print v(vcc)
.endc
.end
""",
    )
    run(
        "diode sub=vcc",
        f"""
Vcc vcc 0 5
Q1 vcc vcc 0 vcc {npn} area=1
Ib vcc vcc 1u
.control
op
print v(vcc)
.endc
.end
""",
    )

    # Forward-active: C=VCC, B=mid, E=0
    run(
        "FA area=1",
        f"""
Vcc vcc 0 5
Vb vb 0 0.7
Q1 vcc vb 0 0 {npn} area=1
Rc vcc vcc 1Meg
.control
op
print v(vb)
print i(vcc)
.endc
.end
""",
    )

    # PTAT core — Brokaw-style shared base
    run(
        "PTAT ΔVbe",
        f"""
Vcc vcc 0 5
Q1 c1 base 0 0 {npn} area=1
Q2 c2 base e2 0 {npn} area=8
Rptat e2 0 10k
Rc1 vcc c1 100k
Rc2 vcc c2 100k
Ib vcc base 1u
.control
op
print v(base)
print v(e2)
print v(base)-v(e2)
.endc
.end
""",
    )

    # Temp sweep Vbe
    run(
        "Vbe vs temp area=1",
        f"""
Vcc vcc 0 3
Q1 vcc vcc em 0 {npn} area=1
Rem em 0 1k
.control
dc temp -40 125 20
print v(vcc)-v(em)
.endc
.end
""",
    )


if __name__ == "__main__":
    main()
