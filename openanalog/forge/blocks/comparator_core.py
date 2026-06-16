"""Full comparator signal path composed from named blocks."""

from __future__ import annotations

from openanalog.forge.blocks.base import BlockMeta, BlockResult
from openanalog.forge.blocks.comparator_output import emit as emit_output
from openanalog.forge.blocks.current_mirror import emit_pmos_load
from openanalog.forge.blocks.differential_pair import emit as emit_diff_pair
from openanalog.forge.blocks.tail_current_source import emit as emit_tail
from openanalog.sim.models import ResolvedModels


def emit(ms: ResolvedModels, *, cross_coupled: bool = False) -> BlockResult:
    """Emit comparator core netlist in legacy device order (M7 before diff pair)."""
    tail = emit_tail(ms)
    diff = emit_diff_pair(ms)
    mirror = emit_pmos_load(ms, cross_coupled=cross_coupled)
    out = emit_output(ms)
    m7, m6, rload = out.lines
    lines = tail.lines + [m7] + diff.lines + mirror.lines + [m6, rload]
    return BlockResult(
        lines=lines,
        meta=BlockMeta(
            block_type="comparator_core",
            devices=tail.meta.devices + diff.meta.devices + mirror.meta.devices + out.meta.devices,
            extra={
                "cross_coupled": cross_coupled,
                "blocks": [tail.meta, diff.meta, mirror.meta, out.meta],
            },
        ),
    )
