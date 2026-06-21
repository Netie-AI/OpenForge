#!/usr/bin/env python3
"""Santunu self-biased PNP bandgap (no ideal opamp)."""
from __future__ import annotations

import os

from openanalog.forge.topologies.base import grab_meas, run_ngspice
from openanalog.sim.models import mos_line, resolve_models, set_active_model_set


def deck(rptat: float, rscale: float) -> str:
    ms = resolve_models()
    return "\n".join(
        [
            ms.block,
            f".param RPTAT={rptat} RSCALE={rscale}",
            "Vsup vdd 0 5",
            mos_line("mp1", "net1", "net2", "vdd", "vdd", "p", w="16u", l="1.5u", ms=ms),
            mos_line("mp2", "ra1", "net2", "vdd", "vdd", "p", w="16u", l="1.5u", ms=ms),
            mos_line("mp3", "vref", "net2", "vdd", "vdd", "p", w="16u", l="1.5u", ms=ms),
            mos_line("mn1", "net1", "net1", "qp1", "0", "n", w="28u", l="0.5u", ms=ms),
            mos_line("mn2", "ra1", "net1", "qp2", "0", "n", w="28u", l="0.5u", ms=ms),
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
    best = None
    for rptat in (600, 800, 1000, 1200, 1500):
        for rscale in range(6000, 11000, 200):
            ok, out = run_ngspice(deck(rptat, rscale), timeout=35)
            vref = grab_meas("vref_nom", out)
            lr = grab_meas("line_reg", out)
            if vref is None:
                continue
            lr_mv = (lr or 0) * 1000
            score = abs(vref - 1.2) + lr_mv / 50
            if best is None or score < best[0]:
                best = (score, rptat, rscale, vref, lr_mv)
    if best:
        _, rptat, rscale, vref, lr_mv = best
        print(f"best Rptat={rptat} Rscale={rscale} vref={vref:.4f} lr={lr_mv:.2f}mV")


if __name__ == "__main__":
    main()
