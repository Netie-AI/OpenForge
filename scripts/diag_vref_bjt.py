#!/usr/bin/env python3
"""Sanity-check SKY130 parasitic BJT Vbe vs area/temp before bandgap sizing."""
from __future__ import annotations

import os
import sys

from openanalog.forge.topologies.base import grab_meas, run_ngspice
from openanalog.sim.models import resolve_models, set_active_model_set


def _vbe_deck(area: float, temp_c: float = 27) -> str:
    ms = resolve_models()
    return f"""{ms.block}
.temp {temp_c}
Vcc vcc 0 3
Ib vcc nc 5u
Q1 vc vb ve 0 {ms.npn} area={area}
Rc vcc vc 1k
Rbe vb ve 1Meg
Re ve 0 10k
.control
op
print v(vb)-v(ve)
.endc
.end
"""


def main() -> int:
    os.environ.setdefault("OPENFORGE_MODEL_SET", "sky130")
    set_active_model_set("sky130")
    ms = resolve_models()
    print(f"model_set={ms.model_set} npn={ms.npn}")

    for area in (1, 8):
        ok, out = run_ngspice(_vbe_deck(area), timeout=20)
        vbe = grab_meas("", out)  # won't work for print
        # parse last v(vb)-v(ve) from print
        for line in out.splitlines():
            if "v(vb)-v(ve)" in line.lower() or line.strip().startswith("v(vb)"):
                print(f"area={area}: {line.strip()}")
        if not ok:
            print(f"area={area} FAILED: {out[:400]}")
            return 1

    # ΔVbe between area=1 and area=8 at same current (approx)
    deck = f"""{ms.block}
Vcc vcc 0 3
* equal-current pair: Q1 small, Q2 large, shared base
Q1 c1 base 0 0 {ms.npn} area=1
Q2 c2 base e2 0 {ms.npn} area=8
Rptat e2 0 5000
Rc1 vcc c1 50k
Rc2 vcc c2 50k
Ib vcc base 2u
.control
op
print v(base)-v(0)
print v(e2)-v(0)
print v(base)-v(e2)
.endc
.end
"""
    ok, out = run_ngspice(deck, timeout=20)
    print("--- PTAT pair ---")
    for line in out.splitlines():
        if "v(" in line.lower() and "=" in line:
            print(line.strip())
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
