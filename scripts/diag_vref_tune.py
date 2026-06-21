#!/usr/bin/env python3
"""Fine sweep PNP bandgap; compare ideal vs MOS opamp."""
from __future__ import annotations

import os

from openanalog.forge.topologies.base import grab_meas, run_ngspice
from openanalog.sim.models import mos_line, resolve_models, set_active_model_set


def deck_ideal(rptat: float, rscale: float, iref_uA: float = 8.0) -> str:
    ms = resolve_models()
    return _body(ms, rptat, rscale, iref_uA, opamp="Eop net2 0 ra1 qp1 800")


def deck_mos(rptat: float, rscale: float, iref_uA: float = 8.0) -> str:
    ms = resolve_models()
    mos_amp = "\n".join(
        [
            mos_line("n1", "ra1", "nb", "0", "0", "n", w="10u", l="0.5u", ms=ms),
            mos_line("n2", "qp1", "nb", "0", "0", "n", w="10u", l="0.5u", ms=ms),
            mos_line("p1", "net2", "qp1", "vdd", "vdd", "p", w="20u", l="1u", ms=ms),
            mos_line("p2", "net2", "ra1", "vdd", "vdd", "p", w="20u", l="1u", ms=ms),
            mos_line("n3", "net2", "nb", "0", "0", "n", w="10u", l="0.5u", ms=ms),
            "Ibias vdd nb {IREF}",
            mos_line("nb", "nb", "nb", "0", "0", "n", w="4u", l="0.5u", ms=ms),
        ]
    )
    return _body(ms, rptat, rscale, iref_uA, opamp=mos_amp)


def _body(ms, rptat: float, rscale: float, iref_uA: float, opamp: str) -> str:
    mirror = "\n".join(
        [
            mos_line("mp1", "qp1", "net2", "vdd", "vdd", "p", w="14u", l="1u", ms=ms),
            mos_line("mp2", "ra1", "net2", "vdd", "vdd", "p", w="14u", l="1u", ms=ms),
            mos_line("mp3", "vref", "net2", "vdd", "vdd", "p", w="14u", l="1u", ms=ms),
        ]
    )
    if opamp.startswith("Eop"):
        tail = "\n".join([opamp, mirror, "Iref vdd net2 {IREF}", mos_line("n0", "net2", "net2", "0", "0", "n", w="5u", l="0.5u", ms=ms)])
    else:
        tail = opamp + "\n" + mirror
    return "\n".join(
        [
            ms.block,
            f".param RPTAT={rptat} RSCALE={rscale} IREF={iref_uA}u",
            "Vsup vdd 0 5",
            tail,
            f"Q1 0 0 qp1 0 {ms.pnp} area=1",
            f"Q2 0 0 qp2 0 {ms.pnp} area=8",
            f"Q3 0 0 qp3 0 {ms.pnp} area=1",
            "Rptat ra1 qp2 {RPTAT}",
            "Rscale vref qp3 {RSCALE}",
            "Cout vref 0 10p",
            ".control",
            "set filetype=ascii",
            "op",
            "let isupp = abs(i(vsup))",
            "print isupp",
            "dc Vsup 3 5.5 0.05",
            "meas dc vref_nom find v(vref) when v(vdd)=5",
            "meas dc line_reg pp v(vref)",
            ".endc",
            ".end",
        ]
    ) + "\n"


def sweep(label: str, builder) -> None:
    print(f"=== {label} ===")
    best = None
    for rptat in (800, 1000, 1200):
        for rscale in range(7000, 10000, 200):
            for ib in (5, 8, 10, 12):
                ok, out = run_ngspice(builder(rptat, rscale, ib), timeout=35)
                vref = grab_meas("vref_nom", out)
                lr = grab_meas("line_reg", out)
                if vref is None:
                    continue
                lr_mv = (lr or 0) * 1000
                score = abs(vref - 1.2) + lr_mv / 100
                if best is None or score < best[0]:
                    best = (score, rptat, rscale, ib, vref, lr_mv)
    if best:
        _, rptat, rscale, ib, vref, lr_mv = best
        print(f"  best Rptat={rptat} Rscale={rscale} Ib={ib} vref={vref:.4f} lr={lr_mv:.2f}mV")


def main() -> None:
    os.environ.setdefault("OPENFORGE_MODEL_SET", "sky130")
    set_active_model_set("sky130")
    sweep("ideal", deck_ideal)
    sweep("mos", deck_mos)


if __name__ == "__main__":
    main()
