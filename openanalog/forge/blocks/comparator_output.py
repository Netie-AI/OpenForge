"""Comparator output stage: NMOS pull-down + PMOS inverter + load resistor."""

from __future__ import annotations

from openanalog.forge.blocks.base import BlockMeta, BlockResult
from openanalog.sim.models import ResolvedModels, mos_inst


def emit(
    ms: ResolvedModels,
    *,
    vdd: str = "vdd",
    nb: str = "nb",
    drive: str = "nout1",
    vout: str = "vout",
    w6_param: str = "W6",
    l6_param: str = "L6",
    w7_param: str = "W7",
    l7_param: str = "L7",
    rload_param: str = "RLOAD",
    inst_pmos: str = "M6",
    inst_nmos: str = "M7",
    rload_name: str = "Rload",
) -> BlockResult:
    lines = [
        mos_inst(
            ms, inst_nmos, vout, nb, "0", "0", "n",
            w=f"{{{w7_param}}}", l=f"{{{l7_param}}}",
        ),
        mos_inst(
            ms, inst_pmos, vout, drive, vdd, vdd, "p",
            w=f"{{{w6_param}}}", l=f"{{{l6_param}}}",
        ),
        f"{rload_name} {vout} 0 {{{rload_param}}}",
    ]
    return BlockResult(
        lines=lines,
        meta=BlockMeta(
            block_type="comparator_output",
            devices=[inst_nmos, inst_pmos, rload_name],
            nodes={"vdd": vdd, "nb": nb, "drive": drive, "vout": vout},
        ),
    )
