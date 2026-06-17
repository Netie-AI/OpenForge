"""Parse SPICE netlists and render device-level SVG schematics."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_MOS_RE = re.compile(
    r"^\s*([Mm]\w+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)",
)
_TWO_TERM_RE = re.compile(r"^\s*([CcRrIi])(\w+)\s+(\S+)\s+(\S+)")
_VSRC_RE = re.compile(r"^\s*([Vv]\w+)\s+(\S+)\s+(\S+)")


@dataclass
class SpiceDevice:
    name: str
    kind: str
    nodes: list[str]
    model: str = ""

    @property
    def label(self) -> str:
        if self.kind == "M":
            d, g, s = self.nodes[:3]
            return f"{self.name}\nd={d} g={g}\ns={s}"
        n1, n2 = self.nodes[0], self.nodes[1] if len(self.nodes) > 1 else "?"
        return f"{self.name}\n{n1}–{n2}"


def parse_spice_devices(netlist: str) -> list[SpiceDevice]:
    devices: list[SpiceDevice] = []
    for raw in (netlist or "").splitlines():
        line = raw.strip()
        if not line or line.startswith(("*", ".")):
            continue
        m = _MOS_RE.match(line)
        if m:
            devices.append(
                SpiceDevice(
                    name=m.group(1),
                    kind="M",
                    nodes=[m.group(2), m.group(3), m.group(4), m.group(5)],
                    model=m.group(6),
                )
            )
            continue
        m = _TWO_TERM_RE.match(line)
        if m:
            devices.append(SpiceDevice(name=m.group(1) + m.group(2), kind=m.group(1).upper(), nodes=[m.group(3), m.group(4)]))
            continue
        m = _VSRC_RE.match(line)
        if m:
            devices.append(SpiceDevice(name=m.group(1), kind="V", nodes=[m.group(2), m.group(3)]))
    return devices


def render_netlist_graph_svg(netlist: str, result: dict[str, Any] | None = None) -> str | None:
    """Device-level schematic from netlist connectivity. Returns None if too sparse."""
    devices = parse_spice_devices(netlist)
    mos = [d for d in devices if d.kind == "M"]
    if len(mos) < 2:
        return None

    from openanalog.eda.schematic_layout import render_schematic_svg

    return render_schematic_svg(devices, result)
