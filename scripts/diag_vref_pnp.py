#!/usr/bin/env python3
"""SKY130 PNP substrate BJT bandgap (academic CMOS topology)."""
from __future__ import annotations

import os

from openanalog.forge.topologies.base import grab_meas, run_ngspice
from openanalog.sim.models import mos_line, resolve_models, set_active_model_set


def deck_pnp(rptat: float, rscale: float, iref_uA: float = 8.0) -> str:
    ms = resolve_models()
    return f"""{ms.block}
.param RPTAT={rptat} RSCALE={rscale} IREF={iref_uA}u
Vsup vdd 0 5
* PMOS mirror: qp1 branch + PTAT resistor branch + output
{mos_line("p0", "vdd", "ng", "vdd", "vdd", "p", w="12u", l="1u", ms=ms)}
{mos_line("p1", "e1", "ng", "vdd", "vdd", "p", w="12u", l="1u", ms=ms)}
{mos_line("p2", "e2", "ng", "vdd", "vdd", "p", w="12u", l="1u", ms=ms)}
{mos_line("p3", "vref", "ng", "vdd", "vdd", "p", w="12u", l="1u", ms=ms)}
Iref vdd ng {{IREF}}
{mos_line("n0", "ng", "ng", "0", "0", "n", w="4u", l="0.5u", ms=ms)}
* Substrate PNP: C=B=0, E=signal (SKY130 style)
Q1 0 0 e1 0 {ms.pnp} area=1
Q2 0 0 e2 0 {ms.pnp} area=8
Rptat e2 e1 {{RPTAT}}
* Opamp servo: equalize mirror drain voltages
Eop e1 0 e2 0 500
Rscale vref e1 {{RSCALE}}
Cout vref 0 10p
.control
set filetype=ascii
op
print v(vref) v(e1) v(e2)
let isupp = abs(i(vsup))
print isupp
dc Vsup 3 5.5 0.05
meas dc vref_nom find v(vref) when v(vdd)=5
meas dc line_reg pp v(vref)
.endc
.end
"""


def deck_npn_follower(rptat: float, rscale: float, iref_uA: float = 8.0) -> str:
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
* Output: Rscale lifts vref above nptat; Rleak provides DC path
Rscale vref nptat {{RSCALE}}
Rleak vref 0 500k
Cout vref 0 10p
.control
set filetype=ascii
op
print v(vref) v(base) v(nptat)
dc Vsup 3 5.5 0.05
meas dc vref_nom find v(vref) when v(vdd)=5
meas dc line_reg pp v(vref)
.endc
.end
"""


def main() -> None:
    os.environ.setdefault("OPENFORGE_MODEL_SET", "sky130")
    set_active_model_set("sky130")
    print("=== NPN Rscale to nptat + Rleak ===")
    for rptat in (800, 1000, 1500):
        for rscale in (8000, 12000, 18000):
            ok, out = run_ngspice(deck_npn_follower(rptat, rscale), timeout=35)
            vref = grab_meas("vref_nom", out)
            lr = grab_meas("line_reg", out)
            if vref:
                print(f"Rptat={rptat} Rscale={rscale} vref={vref:.4f} lr={(lr or 0)*1000:.2f}mV")
    print("=== PNP academic ===")
    for rptat in (800, 1000, 1500):
        for rscale in (8000, 12000, 18000):
            ok, out = run_ngspice(deck_pnp(rptat, rscale), timeout=35)
            vref = grab_meas("vref_nom", out)
            lr = grab_meas("line_reg", out)
            if vref:
                print(f"Rptat={rptat} Rscale={rscale} vref={vref:.4f} lr={(lr or 0)*1000:.2f}mV")


if __name__ == "__main__":
    main()
