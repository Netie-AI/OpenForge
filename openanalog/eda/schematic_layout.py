"""Role-based schematic floorplans, placement, and orthogonal wire routing."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from openanalog.eda.netlist_graph import SpiceDevice
from openanalog.eda.schematic_router import route_nets, segments_to_svg_lines
from openanalog.eda.symbols import Point, render_symbol, snap, terminal_positions

log = logging.getLogger(__name__)

_WIRE_CLASS = 'class="signal-wire"'
_RAIL_CLASS = 'class="signal-wire rail"'
_DOT = 'fill="#5ad1c9"'
_DIM = 'class="dim" fill="#8a97ad"'
_TITLE = 'class="title" fill="#5ad1c9"'
_VDD_LABEL = 'class="rail-label" fill="#5ad1c9"'
_MONO = 'class="mono" fill="#d6deeb"'
_MILLER = 'class="mono" fill="#ffcc66"'

_SVG_STYLES = """<style>
  .signal-wire{stroke:#5ad1c9;stroke-width:1.5;fill:none}
  .signal-wire.rail{stroke-width:2}
  .dim{font:9px ui-monospace,monospace}
  .title{font:bold 13px sans-serif}
  .rail-label{font:bold 11px sans-serif}
  .mono{font:10px ui-monospace,monospace}
</style>"""

# Topology names with defined floorplans.
_FLOORPLAN_TOPOLOGIES = frozenset({"two_stage_miller_opamp", "diff_pair_comparator"})

# Shared diff-pair floorplan (op-amp + comparator).
_DIFF_PAIR_LAYOUT: dict[str, tuple[str, int, bool]] = {
    "M3": ("load", 0, False),
    "M4": ("load", 1, True),
    "M6": ("output", 0, False),
    "M7": ("output", 1, False),
    "M1": ("input", 0, False),
    "M2": ("input", 1, True),
    "M5": ("tail", 0, False),
    "M8": ("bias", 0, False),
    "Iref": ("bias", 1, False),
    "Cc": ("miller", 0, False),
    "Rload": ("output", 2, False),
}

_ZONE_Y = {
    "load": 120,
    "input": 230,
    "tail": 320,
    "bias": 400,
    "output": 120,
    "miller": 175,
}

_ZONE_X: dict[str, list[int]] = {
    "load": [140, 340, 460],
    "input": [140, 340],
    "tail": [240],
    "bias": [160, 320],
    "output": [460, 460, 500],
    "miller": [400],
}


@dataclass
class PlacedDevice:
    dev: SpiceDevice
    origin: Point
    mirror: bool = False


@dataclass
class SchematicLayout:
    width: int
    height: int
    placed: list[PlacedDevice] = field(default_factory=list)
    floorplan_defined: bool = True
    topology: str = ""
    title_suffix: str = "schematic"


def _expand_device_roles(meta: list[dict[str, Any]]) -> dict[str, str]:
    roles: dict[str, str] = {}
    for entry in meta:
        role = str(entry.get("role", ""))
        for part in re.split(r"[/,\s]+", str(entry.get("name", ""))):
            if part:
                roles[part.upper()] = role
    return roles


def _role_zone(role: str) -> str | None:
    r = role.lower()
    if "input" in r or "diff pair" in r:
        return "input"
    if "mirror" in r or "load" in r:
        return "load"
    if "2nd stage" in r or "output" in r:
        return "output"
    if "tail" in r:
        return "tail"
    if "bias" in r or "diode" in r:
        return "bias"
    if "miller" in r or "cap" in r:
        return "miller"
    if "sink" in r:
        return "output"
    return None


def _layout_from_roles(devices: list[SpiceDevice], roles: dict[str, str]) -> dict[str, tuple[str, int, bool]]:
    zone_slots: dict[str, int] = {}
    layout: dict[str, tuple[str, int, bool]] = {}
    for dev in devices:
        role = roles.get(dev.name.upper(), "")
        zone = _role_zone(role)
        if not zone:
            continue
        slot = zone_slots.get(zone, 0)
        mirror = zone == "input" and slot == 1
        layout[dev.name.upper()] = (zone, slot, mirror)
        zone_slots[zone] = slot + 1
    return layout


def _resolve_layout(
    devices: list[SpiceDevice],
    topology: str,
    device_meta: list[dict[str, Any]],
) -> tuple[dict[str, tuple[str, int, bool]], bool]:
    topo = (topology or "").lower()
    if topo in _FLOORPLAN_TOPOLOGIES:
        layout = {k.upper(): v for k, v in _DIFF_PAIR_LAYOUT.items()}
        return layout, True

    roles = _expand_device_roles(device_meta)
    if roles:
        layout = _layout_from_roles(devices, roles)
        if layout:
            log.info("floorplan not yet defined for %s; using role-derived placement", topology or "unknown")
            return layout, False

    log.info("floorplan not yet defined for %s; using fallback grid", topology or "unknown")
    return {}, False


def _place_devices(
    devices: list[SpiceDevice],
    layout: dict[str, tuple[str, int, bool]],
    *,
    floorplan_defined: bool,
) -> list[PlacedDevice]:
    placed: list[PlacedDevice] = []
    if layout:
        for dev in devices:
            spec = layout.get(dev.name.upper())
            if not spec:
                continue
            zone, slot, mirror = spec
            xs = _ZONE_X.get(zone, [200])
            ys = _ZONE_Y.get(zone, 200)
            x = xs[min(slot, len(xs) - 1)]
            y = ys
            if dev.name.upper() == "M7":
                y = 200
            if dev.name.upper() == "Cc":
                y = _ZONE_Y["miller"]
            placed.append(PlacedDevice(dev, Point(snap(x), snap(y)), mirror=mirror))
        if not floorplan_defined:
            missing = [d for d in devices if d.name.upper() not in layout]
            if missing:
                _place_grid(placed, missing, start_row=5)
        return placed

    _place_grid(placed, devices, start_row=0)
    return placed


def _place_grid(placed: list[PlacedDevice], devices: list[SpiceDevice], *, start_row: int) -> None:
    cols = min(4, max(2, int(len(devices) ** 0.5) + 1))
    for i, dev in enumerate(devices):
        col, row = i % cols, i // cols + start_row
        placed.append(PlacedDevice(dev, Point(snap(40 + col * 130), snap(80 + row * 90))))


def _collect_net_points(placed: list[PlacedDevice]) -> dict[str, list[Point]]:
    nets: dict[str, list[Point]] = {}
    for pd in placed:
        for node, pt in terminal_positions(pd.dev, pd.origin, mirror=pd.mirror).items():
            if node == "0":
                continue
            nets.setdefault(node.lower(), []).append(pt)
    return nets


def _vdd_nodes(nets: dict[str, list[Point]]) -> list[Point]:
    return nets.get("vdd", []) + nets.get("vdd3", [])


def _gnd_points(placed: list[PlacedDevice]) -> list[Point]:
    pts: list[Point] = []
    for pd in placed:
        tmap = terminal_positions(pd.dev, pd.origin, mirror=pd.mirror)
        for node, pt in tmap.items():
            if node == "0":
                pts.append(pt)
    return pts


def _draw_rails(
    placed: list[PlacedDevice],
    nets: dict[str, list[Point]],
    width: int,
    height: int,
) -> str:
    body = ""
    margin = 40
    vdd_y = snap(50)
    gnd_y = snap(height - 40)

    vdd_pts = _vdd_nodes(nets)
    if vdd_pts:
        body += f'<line x1="{margin}" y1="{vdd_y}" x2="{width - margin}" y2="{vdd_y}" {_RAIL_CLASS}/>\n'
        body += f'<text x="{margin}" y="{vdd_y - 8}" {_VDD_LABEL}>VDD</text>\n'
        for pt in vdd_pts:
            stub_x = pt.x
            body += f'<line x1="{stub_x}" y1="{vdd_y}" x2="{stub_x}" y2="{pt.y}" {_WIRE_CLASS}/>\n'

    gnd_pts = _gnd_points(placed)
    if gnd_pts:
        body += f'<line x1="{margin}" y1="{gnd_y}" x2="{width - margin}" y2="{gnd_y}" {_RAIL_CLASS}/>\n'
        body += f'<text x="{margin}" y="{gnd_y + 16}" {_DIM}>GND</text>\n'
        for pt in gnd_pts:
            stub_x = pt.x
            body += f'<line x1="{stub_x}" y1="{pt.y}" x2="{stub_x}" y2="{gnd_y}" {_WIRE_CLASS}/>\n'

    return body


def _draw_miller_cap(dev: SpiceDevice, origin: Point) -> str:
    ox, oy = origin.x, origin.y
    return (
        f'<line x1="{ox}" y1="{oy}" x2="{ox + 20}" y2="{oy + 30}" stroke="#ffcc66" stroke-width="1.5"/>\n'
        f'<line x1="{ox + 24}" y1="{oy + 26}" x2="{ox + 24}" y2="{oy + 34}" stroke="#ffcc66" stroke-width="2"/>\n'
        f'<line x1="{ox + 30}" y1="{oy + 26}" x2="{ox + 30}" y2="{oy + 34}" stroke="#ffcc66" stroke-width="2"/>\n'
        f'<line x1="{ox + 34}" y1="{oy + 30}" x2="{ox + 54}" y2="{oy}" stroke="#ffcc66" stroke-width="1.5"/>\n'
        f'<text x="{ox + 8}" y="{oy + 48}" {_MILLER}>{dev.name}</text>\n'
    )


def _io_terminals(placed: list[PlacedDevice]) -> dict[str, Point]:
    """Map external net names to the device terminal they must reach."""
    io: dict[str, Point] = {}
    for pd in placed:
        for node, pt in terminal_positions(pd.dev, pd.origin, mirror=pd.mirror).items():
            nl = node.lower()
            if nl in ("vinp", "vinn"):
                io[nl] = pt
            elif nl == "vout" and (nl not in io or pd.dev.kind == "M"):
                io[nl] = pt
    return io


def _pin_labels(placed: list[PlacedDevice], topology: str, width: int) -> str:
    labels = ""
    topo = topology.lower()
    if topo not in _FLOORPLAN_TOPOLOGIES and "opamp" not in topo and "comparator" not in topo:
        return labels

    io = _io_terminals(placed)
    if "vinp" in io:
        g = io["vinp"]
        labels += f'<text x="50" y="{g.y + 4}" {_DIM}>IN+</text>\n'
        labels += (
            f'<line x1="70" y1="{g.y}" x2="{g.x}" y2="{g.y}" class="signal-wire io-stub"/>\n'
        )
    if "vinn" in io:
        g = io["vinn"]
        ext_x = max(width - 70, g.x + 40)
        labels += f'<text x="{ext_x + 8}" y="{g.y + 4}" {_DIM}>IN-</text>\n'
        labels += (
            f'<line x1="{ext_x}" y1="{g.y}" x2="{g.x}" y2="{g.y}" class="signal-wire io-stub"/>\n'
        )
    if "vout" in io:
        g = io["vout"]
        ext_x = max(width - 70, g.x + 20)
        labels += f'<text x="{ext_x + 10}" y="{g.y + 4}" {_DIM}>OUT</text>\n'
        labels += (
            f'<line x1="{ext_x}" y1="{g.y}" x2="{g.x}" y2="{g.y}" class="signal-wire io-stub"/>\n'
        )
    return labels


def build_schematic_layout(
    devices: list[SpiceDevice],
    result: dict[str, Any] | None = None,
) -> SchematicLayout:
    result = result or {}
    topology = str(result.get("topology") or result.get("category") or "")
    device_meta = result.get("devices") or []

    layout_map, floorplan_defined = _resolve_layout(devices, topology, device_meta)
    placed = _place_devices(devices, layout_map, floorplan_defined=floorplan_defined)

    max_x = max((pd.origin.x + 60 for pd in placed), default=400)
    max_y = max((pd.origin.y + 70 for pd in placed), default=300)
    width = snap(max(520, max_x + 60))
    height = snap(max(460, max_y + 80))

    suffix = "schematic" if floorplan_defined else "schematic (floorplan not yet defined)"
    return SchematicLayout(
        width=width,
        height=height,
        placed=placed,
        floorplan_defined=floorplan_defined,
        topology=topology,
        title_suffix=suffix,
    )


def render_schematic_svg(
    devices: list[SpiceDevice],
    result: dict[str, Any] | None = None,
) -> str:
    """Render role-placed schematic with symbols and orthogonal routing."""
    layout = build_schematic_layout(devices, result)
    body = ""

    for pd in layout.placed:
        if pd.dev.name.upper() == "Cc" and pd.dev.kind == "C":
            body += _draw_miller_cap(pd.dev, pd.origin)
        else:
            body += render_symbol(pd.dev, pd.origin, mirror=pd.mirror)

    routed = route_nets(layout.placed)
    body += segments_to_svg_lines(routed.segments, _WIRE_CLASS, _RAIL_CLASS)
    all_junctions = routed.junctions

    nets = _collect_net_points(layout.placed)
    body += _draw_rails(layout.placed, nets, layout.width, layout.height)
    body += _pin_labels(layout.placed, layout.topology, layout.width)

    for j in all_junctions:
        body += f'<circle cx="{j.x}" cy="{j.y}" r="3" {_DOT}/>\n'

    title = layout.topology or "circuit"
    head = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {layout.width} {layout.height}" width="{layout.width}" height="{layout.height}">
{_SVG_STYLES}
<text x="20" y="22" {_TITLE}>{title} · {layout.title_suffix}</text>
"""
    return head + body + "</svg>"
