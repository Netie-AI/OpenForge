#!/usr/bin/env python3
"""Line-reg diagnosis: headroom vs mirror improvements."""
from __future__ import annotations

import os

from openanalog.forge.topologies.base import grab_meas, run_ngspice
from openanalog.sim.models import mos_line, resolve_models, set_active_model_set


def deck(variant: str, rptat: float = 1000, rscale: float = 8400, ib: float = 5) -> str:
    ms = resolve_models()
    if variant == "cascode":
        mirror = "\n".join(
            [
                mos_line("pc0", "vdd", "ng", "vdd", "vdd", "p", w="16u", l="2u", ms=ms),
                mos_line("pc1", "qp1", "ng", "vdd", "vdd", "p", w="16u", l="2u", ms=ms),
                mos_line("pc2", "ra1", "ng", "vdd", "vdd", "p", w="16u", l="2u", ms=ms),
                mos_line("pc3", "vref", "ng", "vdd", "vdd", "p", w="16u", l="2u", ms=ms),
                mos_line("nc1", "qp1", "qp1", "n1", "0", "n", w="8u", l="0.5u", ms=ms),
                mos_line("nc2", "ra1", "ra1", "n2", "0", "n", w="8u", l="0.5u", ms=ms),
                mos_line("nc3", "vref", "vref", "n3", "0", "n", w="8u", l="0.5u", ms=ms),
                "Iref vdd ng {IREF}",
                mos_line("n0", "ng", "ng", "0", "0", "n", w="6u", l="0.5u", ms=ms),
            ]
        )
    else:
        mirror = "\n".join(
            [
                mos_line("p1", "qp1", "net2", "vdd", "vdd", "p", w="14u", l="1u", ms=ms),
                mos_line("p2", "ra1", "net2", "vdd", "vdd", "p", w="14u", l="1u", ms=ms),
                mos_line("p3", "vref", "net2", "vdd", "vdd", "p", w="14u", l="1u", ms=ms),
                "Iref vdd net2 {IREF}",
                mos_line("n0", "net2", "net2", "0", "0", "n", w="5u", l="0.5u", ms=ms),
            ]
        )
    op = "Eop net2 0 ra1 qp1 800" if variant != "pmos_diff" else "\n".join(
        [
            mos_line("pt", "tail", "tail", "vdd", "vdd", "p", w="8u", l="1u", ms=ms),
            mos_line("pd1", "net2", "ra1", "tail", "vdd", "p", w="24u", l="1u", ms=ms),
            mos_line("pd2", "net2", "qp1", "tail", "vdd", "p", w="24u", l="1u", ms=ms),
            mos_line("nt", "tail", "tail", "0", "0", "n", w="4u", l="0.5u", ms=ms),
        ]
    )
    return "\n".join(
        [
            ms.block,
            f".param RPTAT={rptat} RSCALE={rscale} IREF={ib}u",
            "Vsup vdd 0 5",
            op,
            mirror,
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
            "meas dc lr_hi pp v(vref) from=4.5 to=5.5",
            ".endc",
            ".end",
        ]
    ) + "\n"


def main() -> None:
    os.environ.setdefault("OPENFORGE_MODEL_SET", "sky130")
    set_active_model_set("sky130")
    for v in ("base", "cascode", "pmos_diff"):
        ok, out = run_ngspice(deck(v), timeout=40)
        vref = grab_meas("vref_nom", out)
        lr = grab_meas("line_reg", out)
        lr_hi = grab_meas("lr_hi", out)
        print(
            f"{v}: vref={vref:.4f} full_lr={(lr or 0)*1000:.2f}mV "
            f"4.5-5.5_lr={(lr_hi or 0)*1000:.2f}mV"
        )


if __name__ == "__main__":
    main()
