#!/usr/bin/env python3
"""Test canonical PTAT+CTAT bandgap (no VDD divider on output)."""
from __future__ import annotations

import os

from openanalog.forge.topologies.base import grab_meas, run_ngspice
from openanalog.sim.models import resolve_models, set_active_model_set


def deck(rptat: float, rscale: float, ibias_uA: float, rc: float = 80e3) -> str:
    ms = resolve_models()
    return f"""{ms.block}
.param RPTAT={rptat} RSCALE={rscale} IBIAS={ibias_uA}u RC={rc}
Vsup vdd 0 5
Ibias vdd nbase {{IBIAS}}
Q1 c1 nbase 0 0 {ms.npn} area=1
Q2 c2 nbase nptat 0 {ms.npn} area=8
Rptat nptat 0 {{RPTAT}}
Rc1 vdd c1 {{RC}}
Rc2 vdd c2 {{RC}}
Q3 vref nbase 0 0 {ms.npn} area=1
Rscale vref nptat {{RSCALE}}
Cout vref 0 10p
.control
set filetype=ascii
op
print v(vref)
print v(nptat)
print v(nbase)
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
    for rptat in (2000, 5000, 10000, 20000):
        for rscale in (15000, 25000, 35000, 50000):
            for ib in (3, 5, 8, 12):
                ok, out = run_ngspice(deck(rptat, rscale, ib), timeout=35)
                vref = grab_meas("vref_nom", out)
                lr = grab_meas("line_reg", out)
                if vref is None:
                    print(f"FAIL Rptat={rptat} Rscale={rscale} Ib={ib}uA")
                    continue
                lr_mv = (lr or 0) * 1000
                tag = ""
                if lr_mv < 5 and 1.18 <= vref <= 1.22:
                    tag = "PASS"
                elif 1.15 <= vref <= 1.25 and lr_mv < 50:
                    tag = "CLOSE"
                if tag or ib == 5 and rptat == 5000:
                    print(
                        f"{tag or '....'} Rptat={rptat} Rscale={rscale} Ib={ib}uA "
                        f"-> vref={vref:.4f} lr={lr_mv:.2f}mV"
                    )


if __name__ == "__main__":
    main()
