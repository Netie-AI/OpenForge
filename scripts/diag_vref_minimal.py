#!/usr/bin/env python3
"""Minimal NPN bandgap: PMOS mirror + ideal base servo + Rscale/Rptat stack."""
from __future__ import annotations

import os

from openanalog.forge.topologies.base import grab_meas, run_ngspice
from openanalog.sim.models import mos_line, resolve_models, set_active_model_set


def deck(rptat: float, rscale: float, iref_uA: float = 8.0) -> str:
    ms = resolve_models()
    return "\n".join(
        [
            ms.block,
            f".param RPTAT={rptat} RSCALE={rscale} IREF={iref_uA}u",
            "Vsup vdd 0 5",
            mos_line("p0", "vdd", "ng", "vdd", "vdd", "p", w="14u", l="1u", ms=ms),
            mos_line("p1", "c1", "ng", "vdd", "vdd", "p", w="14u", l="1u", ms=ms),
            mos_line("p2", "c2", "ng", "vdd", "vdd", "p", w="14u", l="1u", ms=ms),
            "Iref vdd ng {IREF}",
            mos_line("n0", "ng", "ng", "0", "0", "n", w="5u", l="0.5u", ms=ms),
            f"Q1 c1 base 0 0 {ms.npn} area=1",
            f"Q2 c2 base nptat 0 {ms.npn} area=8",
            "Rptat nptat 0 {RPTAT}",
            "Bbase base 0 V={0.68 + 500*(V(c1)-V(c2))}",
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
            ".endc",
            ".end",
        ]
    ) + "\n"


def main() -> None:
    os.environ.setdefault("OPENFORGE_MODEL_SET", "sky130")
    set_active_model_set("sky130")
    ok, out = run_ngspice(deck(1000, 11000), timeout=40)
    for line in out.splitlines():
        if "v(" in line.lower() and "=" in line:
            print(line.strip())
    for rptat in (600, 800, 1000, 1200, 1500):
        for rscale in (8000, 10000, 11000, 12000, 14000):
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
            if mark or rptat == 1000:
                print(f"{mark or '....'} Rptat={rptat} Rscale={rscale} vref={vref:.4f} lr={lr_mv:.2f}mV")


if __name__ == "__main__":
    main()
