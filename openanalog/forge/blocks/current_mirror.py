"""PMOS current mirror load (simple diode-connected or cross-coupled gates)."""

from __future__ import annotations

from openanalog.forge.blocks.base import BlockMeta, BlockResult
from openanalog.sim.models import ResolvedModels, mos_inst


def emit_pmos_load(
    ms: ResolvedModels,
    *,
    vdd: str = "vdd",
    drain_ref: str = "n1",
    drain_out: str = "nout1",
    w_param: str = "W3",
    l_param: str = "L3",
    inst_ref: str = "M3",
    inst_out: str = "M4",
    cross_coupled: bool = False,
) -> BlockResult:
    if cross_coupled:
        gate_ref, gate_out = drain_out, drain_ref
        variant = "cross_coupled"
    else:
        gate_ref, gate_out = drain_ref, drain_ref
        variant = "diode_connected"
    lines = [
        mos_inst(
            ms, inst_ref, drain_ref, gate_ref, vdd, vdd, "p",
            w=f"{{{w_param}}}", l=f"{{{l_param}}}",
        ),
        mos_inst(
            ms, inst_out, drain_out, gate_out, vdd, vdd, "p",
            w=f"{{{w_param}}}", l=f"{{{l_param}}}",
        ),
    ]
    return BlockResult(
        lines=lines,
        meta=BlockMeta(
            block_type="current_mirror",
            devices=[inst_ref, inst_out],
            nodes={"rail": vdd, "iref_node": drain_ref, "iout_node": drain_out},
            mirror_ratio=1.0,
            extra={"variant": variant},
        ),
    )
