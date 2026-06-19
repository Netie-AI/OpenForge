"""Tail current source + bias reference stack (Iref, diode NMOS, tail device)."""

from __future__ import annotations

from openanalog.forge.blocks.base import BlockMeta, BlockResult
from openanalog.sim.models import ResolvedModels, mos_inst


def emit(
    ms: ResolvedModels,
    *,
    vdd: str = "vdd",
    nb: str = "nb",
    tail: str = "tail",
    iref_param: str = "IREF",
    wb_param: str = "Wb",
    lb_param: str = "Lb",
    w5_param: str = "W5",
    l5_param: str = "L5",
    include_supply: bool = True,
) -> BlockResult:
    lines: list[str] = []
    if include_supply:
        lines.append(f"VSUP {vdd} 0 {{VDD}}")
    lines.extend(
        [
            f"Iref {vdd} {nb} {{{iref_param}}}",
            mos_inst(ms, "M8", nb, nb, "0", "0", "n", w=f"{{{wb_param}}}", l=f"{{{lb_param}}}"),
            mos_inst(ms, "M5", tail, nb, "0", "0", "n", w=f"{{{w5_param}}}", l=f"{{{l5_param}}}"),
        ]
    )
    return BlockResult(
        lines=lines,
        meta=BlockMeta(
            block_type="tail_current_source",
            devices=["Iref", "M8", "M5"],
            nodes={"vdd": vdd, "nb": nb, "tail": tail},
        ),
    )
