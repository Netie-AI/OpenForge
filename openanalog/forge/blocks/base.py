"""Composable subcircuit blocks for forge topologies (Phase 6)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from openanalog.sim.models import ResolvedModels


@dataclass
class BlockMeta:
    block_type: str
    devices: list[str] = field(default_factory=list)
    nodes: dict[str, str] = field(default_factory=dict)
    # small-signal placeholders — populated when bench hooks exist
    gm: float | None = None
    ro: float | None = None
    rout: float | None = None
    mirror_ratio: float | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class BlockResult:
    lines: list[str]
    meta: BlockMeta

    @property
    def netlist(self) -> str:
        return "\n".join(self.lines)


def join_blocks(*blocks: BlockResult) -> str:
    return "\n".join(line for block in blocks for line in block.lines)
