#!/usr/bin/env python3
"""Santunu-style self-biased NMOS diff bandgap adapted for vertical NPN."""
from __future__ import annotations

import os

from openanalog.forge.topologies.base import grab_meas, run_ngspice
from openanalog.sim.models import mos_line, resolve_models, set_active_model_set


def deck(rptat: float, rscale: float, iref_uA: float = 10.0) -> str:
    ms = resolve_models()
    m = ms
    lines = [
        f"{ms.block}",
        f".param RPTAT={rptat} RSCALE={rscale} IREF={iref_uA}u",
        "Vsup vdd 0 5",
        mos_line("p1", "c1", "ng", "vdd", "vdd", "p", w="16u", l="1u", ms=m),
        mos_line("p2", "c2", "ng", "vdd", "vdd", "p", w="16u", l="1u", ms=m),
        mos_line("p3", "cout", "ng", "vdd", "vdd", "p", w="16u", l="1u", ms=m),
        "Iref vdd ng {IREF}",
        mos_line("n0", "ng", "ng", "0", "0", "n", w="6u", l="0.5u", ms=m),
        mos_line("n1", "c1", "c1", "0", "0", "n", w="24u", l="0.5u", ms=m),
        mos_line("n2", "c2", "c1", "nptat", "0", "n", w="24u", l="0.5u", ms=m),
        f"Q1 c1 base 0 0 {ms.npn} area=1",
        f"Q2 c2 base nptat 0 {ms.npn} area=8",
        "Rptat nptat 0 {RPTAT}",
        f"Q3 cout base vref 0 {ms.npn} area=1",
        "Rscale vref nptat {RSCALE}",
        "Cout vref 0 10p",
        ".control",
        "set filetype=ascii",
        "op",
        "print v(vref) v(base) v(nptat) v(c1) v(c2)",
        "let isupp = abs(i(vsup))",
        "print isupp",
        "dc Vsup 3 5.5 0.05",
        "meas dc vref_nom find v(vref) when v(vdd)=5",
        "meas dc line_reg pp v(vref)",
        "dc Vsup 5 5 1 temp -40 125 20",
        "meas dc tempco pp v(vref)",
        ".endc",
        ".end",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    os.environ.setdefault("OPENFORGE_MODEL_SET", "sky130")
    set_active_model_set("sky130")
    ok, out = run_ngspice(deck(1000, 12000), timeout=40)
    print("--- OP debug ---")
    for line in out.splitlines():
        if "v(" in line.lower() and "=" in line:
            print(line.strip())
    for rptat in (500, 800, 1000, 1500, 2000):
        for rscale in (6000, 9000, 12000, 15000, 20000):
            ok, out = run_ngspice(deck(rptat, rscale), timeout=40)
            vref = grab_meas("vref_nom", out)
            lr = grab_meas("line_reg", out)
            if vref is None:
                continue
            lr_mv = (lr or 0) * 1000
            mark = "PASS" if lr_mv < 5 and 1.18 <= vref <= 1.22 else ""
            mark = mark or ("CLOSE" if 1.15 <= vref <= 1.25 and lr_mv < 20 else "")
            if mark or rptat == 1000:
                print(f"{mark or '....'} Rptat={rptat} Rscale={rscale} vref={vref:.4f} lr={lr_mv:.2f}mV")


if __name__ == "__main__":
    main()
