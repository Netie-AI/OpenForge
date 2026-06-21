#!/usr/bin/env python3
"""PNP substrate bandgap (Santunu ideal-opamp topology) with builtin SKY130 cards."""
from __future__ import annotations

import os

from openanalog.forge.topologies.base import grab_meas, run_ngspice
from openanalog.sim.models import mos_line, resolve_models, set_active_model_set


def deck(rptat: float, rscale: float, iref_uA: float = 8.0) -> str:
    ms = resolve_models()
    # Simplified ladder: single Rptat + Rscale (full ladder in production if needed)
    return "\n".join(
        [
            ms.block,
            f".param RPTAT={rptat} RSCALE={rscale} IREF={iref_uA}u",
            "Vsup vdd 0 5",
            "* Ideal opamp: servo net2 so V(ra1)=V(qp1)",
            "Eop net2 0 ra1 qp1 800",
            mos_line("p1", "qp1", "net2", "vdd", "vdd", "p", w="14u", l="1u", ms=ms),
            mos_line("p2", "ra1", "net2", "vdd", "vdd", "p", w="14u", l="1u", ms=ms),
            mos_line("p3", "vref", "net2", "vdd", "vdd", "p", w="14u", l="1u", ms=ms),
            "Iref vdd net2 {IREF}",
            mos_line("n0", "net2", "net2", "0", "0", "n", w="5u", l="0.5u", ms=ms),
            f"Q1 0 0 qp1 0 {ms.pnp} area=1",
            f"Q2 0 0 qp2 0 {ms.pnp} area=8",
            f"Q3 0 0 qp3 0 {ms.pnp} area=1",
            "Rptat ra1 qp2 {RPTAT}",
            "Rscale vref qp3 {RSCALE}",
            "Cout vref 0 10p",
            ".control",
            "set filetype=ascii",
            "op",
            "print v(vref) v(qp1) v(ra1) v(qp2) v(qp3)",
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
    ok, out = run_ngspice(deck(1000, 12000), timeout=40)
    for line in out.splitlines():
        if "v(" in line.lower() and "=" in line:
            print(line.strip())
    for rptat in (500, 800, 1000, 1500):
        for rscale in (8000, 12000, 16000, 20000, 24000):
            ok, out = run_ngspice(deck(rptat, rscale), timeout=35)
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
