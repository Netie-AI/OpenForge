#!/usr/bin/env python3
"""Brokaw vref = Vbe + (Rscale/Rptat)*V(nptat) — no Q3, no VDD divider."""
from __future__ import annotations

import os

from openanalog.forge.topologies.base import grab_meas, run_ngspice
from openanalog.sim.models import resolve_models, set_active_model_set


def deck(rptat: float, rscale: float, iref_uA: float = 8.0) -> str:
    ms = resolve_models()
    return f"""{ms.block}
.param RPTAT={rptat} RSCALE={rscale} IREF={iref_uA}u
Vsup vdd 0 5
Mp0 vdd ng ng vdd {ms.pmos} W=12u L=1u
Mp1 c1 ng vdd vdd {ms.pmos} W=12u L=1u
Mp2 c2 ng vdd vdd {ms.pmos} W=12u L=1u
Iref vdd ng {{IREF}}
Mn0 ng ng 0 0 {ms.nmos} W=4u L=0.5u
Q1 c1 base 0 0 {ms.npn} area=1
Q2 c2 base nptat 0 {ms.npn} area=8
Rptat nptat 0 {{RPTAT}}
Bbase base 0 V={{0.68 + 500*(V(c1)-V(c2))}}
Rscale vref base {{RSCALE}}
Cout vref 0 10p
.control
set filetype=ascii
op
print v(vref) v(base) v(nptat)
let isupp = abs(i(vsup))
print isupp
dc Vsup 3 5.5 0.05
meas dc vref_nom find v(vref) when v(vdd)=5
meas dc line_reg pp v(vref)
dc Vsup 5 5 1 temp -40 125 20
meas dc tempco pp v(vref)
.endc
.end
"""


def main() -> None:
    os.environ.setdefault("OPENFORGE_MODEL_SET", "sky130")
    set_active_model_set("sky130")
    for rptat in (500, 800, 1000, 1500, 2000, 3000):
        for rscale in (6000, 9000, 12000, 15000, 18000, 22000):
            ok, out = run_ngspice(deck(rptat, rscale), timeout=35)
            vref = grab_meas("vref_nom", out)
            lr = grab_meas("line_reg", out)
            if vref is None:
                continue
            lr_mv = (lr or 0) * 1000
            mark = ""
            if lr_mv < 5 and 1.18 <= vref <= 1.22:
                mark = "PASS"
            elif 1.15 <= vref <= 1.25 and lr_mv < 20:
                mark = "CLOSE"
            if mark or rptat == 1000 and rscale in (12000, 15000):
                print(f"{mark:5} Rptat={rptat} Rscale={rscale} vref={vref:.4f} lr={lr_mv:.2f}mV")


if __name__ == "__main__":
    main()
