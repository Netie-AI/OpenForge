"""NMOS differential pair."""

from __future__ import annotations

from openanalog.forge.blocks.base import BlockMeta, BlockResult
from openanalog.sim.models import ResolvedModels


def emit(
    ms: ResolvedModels,
    *,
    vinp: str = "vinp",
    vinn: str = "vinn",
    tail: str = "tail",
    out_p: str = "n1",
    out_n: str = "nout1",
    w_param: str = "W1",
    l_param: str = "L1",
    inst_p: str = "M1",
    inst_n: str = "M2",
) -> BlockResult:
    lines = [
        f"{inst_p} {out_p}    {vinp} {tail} 0 {ms.nmos} W={{{w_param}}} L={{{l_param}}}",
        f"{inst_n} {out_n} {vinn} {tail} 0 {ms.nmos} W={{{w_param}}} L={{{l_param}}}",
    ]
    return BlockResult(
        lines=lines,
        meta=BlockMeta(
            block_type="differential_pair",
            devices=[inst_p, inst_n],
            nodes={
                "vin_p": vinp,
                "vin_n": vinn,
                "vtail": tail,
                "vout_p": out_p,
                "vout_n": out_n,
            },
        ),
    )
