#!/usr/bin/env python3
"""Try MOS-assisted Brokaw bandgap — opamp forces equal collector currents."""
from __future__ import annotations

import os

from openanalog.forge.topologies.base import grab_meas, run_ngspice
from openanalog.sim.models import mos_line, resolve_models, set_active_model_set


def deck(rptat: float, rscale: float, ibias_uA: float) -> str:
    ms = resolve_models()
    return f"""{ms.block}
.param RPTAT={rptat} RSCALE={rscale} IBIAS={ibias_uA}u
Vsup vdd 0 5
* Bias / mirror tail
Iref vdd nb {{IBIAS}}
{mos_line("b", "nb", "nb", "0", "0", "n", w="4u", l="0.5u", ms=ms)}
* PMOS mirror: equal currents in Q1/Q2 collectors
{mos_line("p0", "vdd", "ng", "vdd", "vdd", "p", w="12u", l="1u", ms=ms)}
{mos_line("p1", "c1", "ng", "vdd", "vdd", "p", w="12u", l="1u", ms=ms)}
{mos_line("p2", "c2", "ng", "vdd", "vdd", "p", w="12u", l="1u", ms=ms)}
{mos_line("n0", "ng", "ng", "0", "0", "n", w="4u", l="0.5u", ms=ms)}
* PTAT pair
Q1 c1 base 0 0 {ms.npn} area=1
Q2 c2 base nptat 0 {ms.npn} area=8
Rptat nptat 0 {{RPTAT}}
* Simple diff amp: n3/n4 compare c1 vs c2, drive base
{mos_line("n3", "c1", "nb", "0", "0", "n", w="8u", l="0.5u", ms=ms)}
{mos_line("n4", "c2", "nb", "0", "0", "n", w="8u", l="0.5u", ms=ms)}
{mos_line("p3", "nout", "c2", "vdd", "vdd", "p", w="16u", l="1u", ms=ms)}
{mos_line("p4", "nout", "c1", "vdd", "vdd", "p", w="16u", l="1u", ms=ms)}
{mos_line("n5", "nout", "nb", "0", "0", "n", w="8u", l="0.5u", ms=ms)}
* Output stack: Vbe + scaled ΔVbe at vref
Q3 nct vref 0 0 {ms.npn} area=1
Rct vdd nct 200k
Rscale vref nptat {{RSCALE}}
Cout vref 0 10p
.control
set filetype=ascii
op
print v(vref)
print v(base)
print v(nptat)
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
    ms = resolve_models()
    for rptat in (1000, 3000, 6000, 12000):
        for rscale in (20000, 35000, 50000, 80000):
            ok, out = run_ngspice(deck(rptat, rscale, 8), timeout=40)
            vref = grab_meas("vref_nom", out)
            lr = grab_meas("line_reg", out)
            if vref is None:
                continue
            lr_mv = (lr or 0) * 1000
            print(f"Rptat={rptat} Rscale={rscale} vref={vref:.4f} lr={lr_mv:.2f}mV")


if __name__ == "__main__":
    main()
