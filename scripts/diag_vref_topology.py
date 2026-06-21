#!/usr/bin/env python3
"""Probe bandgap topology candidates — structural diagnosis before sizing."""
from __future__ import annotations

import os

from openanalog.forge.topologies.base import grab_meas, run_ngspice
from openanalog.sim.models import mos_line, resolve_models, set_active_model_set


def bandgap_v1(ms, rptat: float, r1: float, r2: float, ibias_uA: float) -> str:
    """Brokaw-style PTAT core + Vbe3 output stack; MOS bias mirror."""
    return f"""{ms.block}
.param RPTAT={rptat} R1={r1} R2={r2} IBIAS={ibias_uA}u
Vsup vdd 0 5
* PMOS mirror biases equal collector currents
{mos_line("p1", "vdd", "nbias", "vdd", "vdd", "p", w="8u", l="1u", ms=ms)}
{mos_line("p2", "c1", "nbias", "vdd", "vdd", "p", w="8u", l="1u", ms=ms)}
{mos_line("p3", "c2", "nbias", "vdd", "vdd", "p", w="8u", l="1u", ms=ms)}
{mos_line("nb", "nbias", "nbias", "0", "0", "n", w="4u", l="0.5u", ms=ms)}
Iref vdd nbias {{IBIAS}}
* PTAT BJT pair (shared base, Q2 larger emitter resistor)
Q1 c1 base 0 0 {ms.npn} area=1
Q2 c2 base nptat 0 {ms.npn} area=8
Rptat nptat 0 {{RPTAT}}
* Output CTAT + PTAT scaling
Q3 vref base 0 0 {ms.npn} area=1
Rtop vdd vref {{R1}}
Rbot vref 0 {{R2}}
Cout vref 0 10p
.control
set filetype=ascii
op
let isupp = abs(i(vsup))
print isupp
dc Vsup 3 5.5 0.1
meas dc vref_nom find v(vref) when v(vdd)=5
meas dc line_reg pp v(vref)
dc Vsup 5 5 1 temp -40 125 20
meas dc tempco pp v(vref)
.endc
.end
"""


def bandgap_v2(ms, rptat: float, r1: float, r2: float, ibias_uA: float) -> str:
    """Resistorless bias PTAT core — diode-connected BJT bias, explicit Vbe stack."""
    return f"""{ms.block}
.param RPTAT={rptat} R1={r1} R2={r2} IBIAS={ibias_uA}u
Vsup vdd 0 5
Ib vdd base {{IBIAS}}
Q1 c1 base 0 0 {ms.npn} area=1
Q2 c2 base nptat 0 {ms.npn} area=8
Rc1 vdd c1 80k
Rc2 vdd c2 80k
Rptat nptat 0 {{RPTAT}}
* vref = Vbe3 + (R2/Rptat)*ΔVbe via resistor from nptat
Q3 nctat base 0 0 {ms.npn} area=1
Rct vdd nctat 200k
Rscale nctat vref {{R1}}
Rload vref 0 {{R2}}
Cout vref 0 10p
.control
set filetype=ascii
op
let isupp = abs(i(vsup))
print isupp
dc Vsup 3 5.5 0.1
meas dc vref_nom find v(vref) when v(vdd)=5
meas dc line_reg pp v(vref)
.endc
.end
"""


def bandgap_v3(ms, rptat: float, r1: float, r2: float, ibias_uA: float) -> str:
    """Classic 1.2V stack: ΔVbe*R2/Rptat added to Q1 Vbe at output."""
    return f"""{ms.block}
.param RPTAT={rptat} R1={r1} R2={r2} IBIAS={ibias_uA}u
Vsup vdd 0 5
Ib vdd base {{IBIAS}}
Q1 c1 base 0 0 {ms.npn} area=1
Q2 c2 base nptat 0 {ms.npn} area=8
Rc1 vdd c1 100k
Rc2 vdd c2 100k
Rptat nptat 0 {{RPTAT}}
* Output: emitter follower + PTAT lift
Qout vref base 0 0 {ms.npn} area=1
Rfb vdd vref {{R1}}
Rpt vref nptat {{R2}}
Cout vref 0 10p
.control
set filetype=ascii
op
let isupp = abs(i(vsup))
print isupp
dc Vsup 3 5.5 0.1
meas dc vref_nom find v(vref) when v(vdd)=5
meas dc line_reg pp v(vref)
.endc
.end
"""


def try_topo(name: str, deck: str) -> None:
    ok, out = run_ngspice(deck, timeout=40)
    vref = grab_meas("vref_nom", out)
    line_reg = grab_meas("line_reg", out)
    isupp = None
    for line in out.splitlines():
        if "isupp" in line and "=" in line:
            try:
                isupp = float(line.split("=")[-1])
            except ValueError:
                pass
    lr_mv = line_reg * 1000 if line_reg else None
    print(
        f"{name}: ok={ok} vref={vref:.4f}V line_reg={lr_mv:.2f}mV iq={isupp*1e6 if isupp else None:.1f}uA"
        if vref
        else f"{name}: ok={ok} FAIL {out[-400:]}"
    )


def main() -> None:
    os.environ.setdefault("OPENFORGE_MODEL_SET", "sky130")
    set_active_model_set("sky130")
    ms = resolve_models()
    # Coarse grid
    for rptat in (3000, 8000, 15000):
        for r1, r2 in ((30e3, 12e3), (50e3, 20e3), (80e3, 30e3)):
            try_topo(f"v1 Rptat={rptat}", bandgap_v1(ms, rptat, r1, r2, 5.0))
            try_topo(f"v3 Rptat={rptat}", bandgap_v3(ms, rptat, r1, r2, 5.0))


if __name__ == "__main__":
    main()
