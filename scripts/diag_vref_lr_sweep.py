#!/usr/bin/env python3
"""Sweep ideal-opamp PNP bandgap for line_reg."""
from __future__ import annotations

import os

from openanalog.forge.topologies.base import grab_meas, run_ngspice
from openanalog.sim.models import mos_line, resolve_models, set_active_model_set


def deck(rptat: float, rscale: float, ib: float, pl: str) -> str:
    ms = resolve_models()
    return "\n".join(
        [
            ms.block,
            f".param RPTAT={rptat} RSCALE={rscale} IREF={ib}u",
            "Vsup vdd 0 5",
            "Eop net2 0 ra1 qp1 800",
            mos_line("p1", "qp1", "net2", "vdd", "vdd", "p", w="20u", l=pl, ms=ms),
            mos_line("p2", "ra1", "net2", "vdd", "vdd", "p", w="20u", l=pl, ms=ms),
            mos_line("p3", "vref", "net2", "vdd", "vdd", "p", w="20u", l=pl, ms=ms),
            "Iref vdd net2 {IREF}",
            mos_line("n0", "net2", "net2", "0", "0", "n", w="6u", l="0.5u", ms=ms),
            f"Q1 0 0 qp1 0 {ms.pnp} area=1",
            f"Q2 0 0 qp2 0 {ms.pnp} area=8",
            f"Q3 0 0 qp3 0 {ms.pnp} area=1",
            "Rptat ra1 qp2 {RPTAT}",
            "Rscale vref qp3 {RSCALE}",
            "Cout vref 0 10p",
            ".control",
            "set filetype=ascii",
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
    best = None
    for pl in ("1u", "2u", "3u", "4u"):
        for rptat in (800, 1000, 1200):
            for rscale in range(7800, 9000, 100):
                for ib in (3, 5, 7):
                    ok, out = run_ngspice(deck(rptat, rscale, ib, pl), timeout=30)
                    vref = grab_meas("vref_nom", out)
                    lr = grab_meas("line_reg", out)
                    if vref is None:
                        continue
                    lr_mv = (lr or 0) * 1000
                    if 1.18 <= vref <= 1.22 and lr_mv < 5:
                        print(f"PASS pl={pl} Rptat={rptat} Rscale={rscale} ib={ib} vref={vref:.4f} lr={lr_mv:.2f}")
                    score = abs(vref - 1.2) + lr_mv / 100
                    if best is None or score < best[0]:
                        best = (score, pl, rptat, rscale, ib, vref, lr_mv)
    if best:
        _, pl, rptat, rscale, ib, vref, lr_mv = best
        print(f"best pl={pl} Rptat={rptat} Rscale={rscale} ib={ib} vref={vref:.4f} lr={lr_mv:.2f}mV")


if __name__ == "__main__":
    main()
