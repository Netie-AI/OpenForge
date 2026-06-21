#!/usr/bin/env python3
"""Brokaw NPN bandgap — sweep shared base to equalize collectors, no VDD divider."""
from __future__ import annotations

import os

from openanalog.forge.topologies.base import grab_meas, run_ngspice
from openanalog.sim.models import resolve_models, set_active_model_set


def deck(rptat: float, rscale: float, vbase: float) -> str:
    ms = resolve_models()
    return f"""{ms.block}
.param RPTAT={rptat} RSCALE={rscale} VBASE={vbase}
Vsup vdd 0 5
Vbase base 0 {{VBASE}}
Q1 c1 base 0 0 {ms.npn} area=1
Q2 c2 base nptat 0 {ms.npn} area=8
Rptat nptat 0 {{RPTAT}}
Rc1 vdd c1 100k
Rc2 vdd c2 100k
Q3 vref base 0 0 {ms.npn} area=1
Rscale vref nptat {{RSCALE}}
Cout vref 0 10p
.control
set filetype=ascii
op
print v(c1) v(c2) v(vref) v(nptat) v(base)
.endc
.end
"""


def sweep_balance() -> float:
    ms = resolve_models()
    best_vb, best_err = 0.7, 1e9
    for vb in [x / 1000 for x in range(550, 850)]:
        ok, out = run_ngspice(deck(1000, 10000, vb), timeout=20)
        if not ok:
            continue
        vc1 = vc2 = None
        for line in out.splitlines():
            if "v(c1)" in line.lower():
                parts = line.split("=")
                if len(parts) == 2:
                    vc1 = float(parts[1].strip())
            if "v(c2)" in line.lower():
                parts = line.split("=")
                if len(parts) == 2:
                    vc2 = float(parts[1].strip())
        if vc1 is not None and vc2 is not None:
            err = abs(vc1 - vc2)
            if err < best_err:
                best_err, best_vb = err, vb
    print(f"balanced Vbase≈{best_vb:.3f} err={best_err:.4f}V")
    return best_vb


def deck_closed(rptat: float, rscale: float) -> str:
    """PMOS mirror + behavioral base servo for equal collector voltages."""
    ms = resolve_models()
    return f"""{ms.block}
.param RPTAT={rptat} RSCALE={rscale}
Vsup vdd 0 5
* PMOS 1:2 mirror biases PTAT pair
Mp0 vdd ng ng vdd {ms.pmos} W=12u L=1u
Mp1 c1 ng vdd vdd {ms.pmos} W=12u L=1u
Mp2 c2 ng vdd vdd {ms.pmos} W=12u L=1u
Iref vdd ng 8u
Mn0 ng ng 0 0 {ms.nmos} W=4u L=0.5u
Q1 c1 base 0 0 {ms.npn} area=1
Q2 c2 base nptat 0 {ms.npn} area=8
Rptat nptat 0 {{RPTAT}}
* Servo base so V(c1)=V(c2) — structural opamp stand-in for diagnosis
Bbase base 0 V={{0.68 + 500*(V(c1)-V(c2))}}
Q3 vref base 0 0 {ms.npn} area=1
Rscale vref nptat {{RSCALE}}
Cout vref 0 10p
.control
set filetype=ascii
op
print v(vref) v(nptat) v(c1) v(c2)
let isupp = abs(i(vsup))
print isupp
dc Vsup 3 5.5 0.05
meas dc vref_nom find v(vref) when v(vdd)=5
meas dc line_reg pp v(vref)
.endc
.end
"""


def main() -> None:
    os.environ.setdefault("OPENFORGE_MODEL_SET", "sky130")
    set_active_model_set("sky130")
    sweep_balance()
    for rptat in (500, 1000, 2000, 5000):
        for rscale in (8000, 12000, 18000, 25000, 35000):
            ok, out = run_ngspice(deck_closed(rptat, rscale), timeout=35)
            vref = grab_meas("vref_nom", out)
            lr = grab_meas("line_reg", out)
            if vref is None:
                continue
            lr_mv = (lr or 0) * 1000
            if 1.1 <= vref <= 1.3 or lr_mv < 20:
                print(f"Rptat={rptat} Rscale={rscale} vref={vref:.4f} lr={lr_mv:.2f}mV")


if __name__ == "__main__":
    main()
