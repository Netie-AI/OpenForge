"""Role-based schematic floorplans, placement, and orthogonal wire routing."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from openanalog.eda.netlist_graph import SpiceDevice
from openanalog.eda.schematic_geometry import DeviceBox, Segment, collinear_overlap, score_layout
from openanalog.eda.schematic_router import _TRACK_PITCH, route_nets, segments_to_svg_lines
from openanalog.eda.symbols import Point, render_symbol, snap, symbol_for_device, terminal_positions, terminal_refs

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

_STAGE2_VARIANTS: dict[str, dict[str, tuple[str, int, bool]]] = {
    "isolated": {"M6": ("output", 0, False), "M7": ("output", 1, False)},
    "tail_aligned": {"M6": ("output", 0, False), "M7": ("tail", 1, False)},
}

_ZONE_Y = {
    "load": 120,
    "input": 230,
    "tail": 320,
    "bias": 400,
    "output": 120,
    # Keep Cc taps above the diff-pair spine to avoid crossing the core row.
    "miller": 160,
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
    variant: str = "default"
    crossing_score: int = -1


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
        _orient_two_terminal_devices(placed)
        return placed

    _place_grid(placed, devices, start_row=0)
    _orient_two_terminal_devices(placed)
    return placed


def _place_grid(placed: list[PlacedDevice], devices: list[SpiceDevice], *, start_row: int) -> None:
    cols = min(4, max(2, int(len(devices) ** 0.5) + 1))
    for i, dev in enumerate(devices):
        col, row = i % cols, i // cols + start_row
        placed.append(PlacedDevice(dev, Point(snap(40 + col * 130), snap(80 + row * 90))))


def _two_terminal_orientation_cost(
    placed: list[PlacedDevice],
    idx: int,
    *,
    mirror: bool,
) -> float:
    """Lower is better: left lead should face left-side target net."""
    pd = placed[idx]
    refs = terminal_refs(pd.dev, pd.origin, mirror=mirror)
    if len(refs) != 2:
        return 0.0

    target_x_by_node: dict[str, float] = {}
    cost = 0.0
    attached = 0
    for node, _, pt in refs:
        xs: list[int] = []
        for j, other in enumerate(placed):
            if j == idx:
                continue
            for onode, _, opt in terminal_refs(other.dev, other.origin, mirror=other.mirror):
                if onode.lower() == node.lower():
                    xs.append(opt.x)
        if not xs:
            continue
        tx = sum(xs) / len(xs)
        target_x_by_node[node.lower()] = tx
        cost += abs(pt.x - tx)
        attached += 1

    if attached == 0:
        return 0.0

    left_ref, right_ref = sorted(refs, key=lambda t: t[2].x)
    left_node = left_ref[0].lower()
    right_node = right_ref[0].lower()
    if left_node in target_x_by_node and right_node in target_x_by_node:
        if target_x_by_node[left_node] > target_x_by_node[right_node]:
            # Backwards assignment (left lead points to right-side net).
            cost += 10_000.0

    return cost


def _orient_two_terminal_devices(placed: list[PlacedDevice]) -> None:
    """Pick horizontal mirror for C/R devices from net geography."""
    for _ in range(2):
        changed = False
        for idx, pd in enumerate(placed):
            if pd.dev.kind not in ("C", "R") or len(pd.dev.nodes) != 2:
                continue
            nom = _two_terminal_orientation_cost(placed, idx, mirror=False)
            mir = _two_terminal_orientation_cost(placed, idx, mirror=True)
            best_mirror = mir < nom
            if pd.mirror != best_mirror:
                pd.mirror = best_mirror
                changed = True
        if not changed:
            break


def _collect_net_points(placed: list[PlacedDevice]) -> dict[str, list[Point]]:
    nets: dict[str, list[Point]] = {}
    for pd in placed:
        for node, _, pt in terminal_refs(pd.dev, pd.origin, mirror=pd.mirror):
            if node == "0":
                continue
            nets.setdefault(node.lower(), []).append(pt)
    return nets


def _vdd_nodes(nets: dict[str, list[Point]]) -> list[Point]:
    return nets.get("vdd", []) + nets.get("vdd3", [])


def _gnd_points(placed: list[PlacedDevice]) -> list[Point]:
    pts: list[Point] = []
    for pd in placed:
        for node, _, pt in terminal_refs(pd.dev, pd.origin, mirror=pd.mirror):
            if node == "0":
                pts.append(pt)
    return pts


def _device_boxes(placed: list[PlacedDevice]) -> list[DeviceBox]:
    boxes: list[DeviceBox] = []
    for pd in placed:
        sym = symbol_for_device(pd.dev)
        width = sym.width
        height = sym.height
        # Cc is rendered by _draw_miller_cap (wider than generic cap symbol).
        if pd.dev.kind == "C" and pd.dev.name.upper() == "CC":
            width = max(width, 54)
            height = max(height, 48)
        terminal_nets = frozenset(
            node.lower() for node, _, _ in terminal_refs(pd.dev, pd.origin, mirror=pd.mirror)
        )
        boxes.append(
            DeviceBox(
                name=pd.dev.name,
                x=pd.origin.x,
                y=pd.origin.y,
                w=width,
                h=height,
                terminal_nets=terminal_nets,
            )
        )
    return boxes


def _segments_for_score(layout: SchematicLayout) -> tuple[list[Segment], set[tuple[int, int]]]:
    routed = route_nets(layout.placed)
    segments: list[Segment] = []
    for s in routed.segments:
        kind = "stub" if s.kind == "stub" else "wire"
        if s.x1 == s.x2 or s.y1 == s.y2:
            segments.append(Segment(x1=s.x1, y1=s.y1, x2=s.x2, y2=s.y2, net=s.net, kind=kind))
            continue
        # Rare fallback path emits diagonal hops; split into two orthogonal legs for scoring.
        corner_x, corner_y = s.x2, s.y1
        segments.append(Segment(x1=s.x1, y1=s.y1, x2=corner_x, y2=corner_y, net=s.net, kind=kind))
        segments.append(Segment(x1=corner_x, y1=corner_y, x2=s.x2, y2=s.y2, net=s.net, kind=kind))
    junctions = {(pt.x, pt.y) for pt in routed.junctions}
    return segments, junctions


def _score_layout(layout: SchematicLayout) -> int:
    segments, junctions = _segments_for_score(layout)
    return score_layout(segments, junctions, _device_boxes(layout.placed))


def _span_pressure_penalty(placed: list[PlacedDevice]) -> int:
    """Penalty for long multi-terminal nets that tend to force cross-canvas wires."""
    penalty = 0
    nets = _collect_net_points(placed)
    for net_name, points in nets.items():
        if net_name in {"vdd", "vdd3", "0"}:
            continue
        unique = {(pt.x, pt.y) for pt in points}
        if len(unique) < 3:
            continue
        xs = [pt[0] for pt in unique]
        ys = [pt[1] for pt in unique]
        span = max(max(xs) - min(xs), max(ys) - min(ys))
        if span <= 120:
            continue
        fanout_weight = max(1, len(unique) - 2)
        # Bias spine (`nb`) is the known pressure net in the opamp floorplan.
        if net_name == "nb":
            fanout_weight += 4
        penalty += fanout_weight * max(1, span // 80)
    return penalty


def _stage2_alignment_penalty(layout: SchematicLayout) -> int:
    """Prefer placing stage-2 load (M7) under/near stage-2 device (M6)."""
    if "opamp" not in (layout.topology or "").lower():
        return 0
    by_name = {pd.dev.name.upper(): pd for pd in layout.placed}
    m6 = by_name.get("M6")
    m7 = by_name.get("M7")
    if m6 is None or m7 is None:
        return 0
    return abs(m7.origin.x - m6.origin.x) // 40


def _placement_objective(layout: SchematicLayout) -> tuple[int, int, int, int]:
    crossing = _score_layout(layout)
    span_penalty = _span_pressure_penalty(layout.placed)
    align_penalty = _stage2_alignment_penalty(layout)
    return (crossing + span_penalty + align_penalty, crossing, align_penalty, span_penalty)


def _choose_opamp_variant(devices: list[SpiceDevice], topology: str) -> tuple[str, int, list[PlacedDevice]]:
    best_variant = "isolated"
    best_score = 10**9
    best_obj = (10**9, 10**9, 10**9, 10**9)
    best_placed: list[PlacedDevice] = []
    for variant_name, stage2 in _STAGE2_VARIANTS.items():
        layout_map = {k.upper(): v for k, v in _DIFF_PAIR_LAYOUT.items()}
        for name, spec in stage2.items():
            layout_map[name.upper()] = spec
        placed = _place_devices(devices, layout_map, floorplan_defined=True)
        trial = SchematicLayout(
            width=0,
            height=0,
            placed=placed,
            floorplan_defined=True,
            topology=topology,
            variant=variant_name,
        )
        obj = _placement_objective(trial)
        score = obj[1]
        log.info(
            "schematic floorplan variant=%s objective=%d crossing_score=%d stage2_align_penalty=%d span_penalty=%d",
            variant_name,
            obj[0],
            obj[1],
            obj[2],
            obj[3],
        )
        if obj < best_obj:
            best_obj = obj
            best_variant = variant_name
            best_score = score
            best_placed = placed

    return best_variant, best_score, best_placed


def _rail_riser_stub_x(
    pt: Point,
    rail_y: int,
    net: str,
    foreign: list[Segment],
    *,
    margin: int = 40,
) -> int:
    """Pick a riser column that does not collinearly overlap foreign signal tracks."""
    candidates = [pt.x]
    for delta in (_TRACK_PITCH, -_TRACK_PITCH, _TRACK_PITCH * 2, -_TRACK_PITCH * 2):
        candidates.append(pt.x + delta)
    for stub_x in candidates:
        if stub_x < margin:
            continue
        probe = rail_riser_segments(pt, rail_y, net, stub_x)
        if not any(collinear_overlap(riser, other) for riser in probe for other in foreign):
            return stub_x
    return pt.x


def rail_riser_segments(
    pt: Point,
    rail_y: int,
    net: str,
    stub_x: int,
) -> list[Segment]:
    """Manhattan legs from a device terminal down/up to a VDD/GND rail."""
    if stub_x == pt.x:
        return [Segment(stub_x, pt.y, stub_x, rail_y, net, "wire")]
    return [
        Segment(pt.x, pt.y, stub_x, pt.y, net, "wire"),
        Segment(stub_x, pt.y, stub_x, rail_y, net, "wire"),
    ]


def all_rail_riser_segments(
    placed: list[PlacedDevice],
    nets: dict[str, list[Point]],
    height: int,
    routed_segments: list,
) -> list[Segment]:
    """Rail riser geometry with the same stub_x avoidance used at render time."""
    vdd_y = snap(50)
    gnd_y = snap(height - 40)
    foreign = [
        Segment(s.x1, s.y1, s.x2, s.y2, s.net, s.kind)
        for s in routed_segments
        if s.kind in ("wire", "stub")
    ]
    out: list[Segment] = []
    for pt in _vdd_nodes(nets):
        stub_x = _rail_riser_stub_x(pt, vdd_y, "vdd", foreign)
        out.extend(rail_riser_segments(pt, vdd_y, "vdd", stub_x))
    for pt in _gnd_points(placed):
        stub_x = _rail_riser_stub_x(pt, gnd_y, "0", foreign)
        out.extend(rail_riser_segments(pt, gnd_y, "0", stub_x))
    return out


def _draw_rail_riser_svg(pt: Point, rail_y: int, net: str, stub_x: int) -> str:
    body = ""
    for seg in rail_riser_segments(pt, rail_y, net, stub_x):
        body += f'<line x1="{seg.x1}" y1="{seg.y1}" x2="{seg.x2}" y2="{seg.y2}" {_WIRE_CLASS}/>\n'
    return body


def _draw_rails(
    placed: list[PlacedDevice],
    nets: dict[str, list[Point]],
    width: int,
    height: int,
    routed_segments: list | None = None,
) -> str:
    body = ""
    margin = 40
    vdd_y = snap(50)
    gnd_y = snap(height - 40)
    foreign = [
        Segment(s.x1, s.y1, s.x2, s.y2, s.net, s.kind)
        for s in (routed_segments or [])
        if s.kind in ("wire", "stub")
    ]

    vdd_pts = _vdd_nodes(nets)
    if vdd_pts:
        body += f'<line x1="{margin}" y1="{vdd_y}" x2="{width - margin}" y2="{vdd_y}" {_RAIL_CLASS}/>\n'
        body += f'<text x="{margin}" y="{vdd_y - 8}" {_VDD_LABEL}>VDD</text>\n'
        for pt in vdd_pts:
            stub_x = _rail_riser_stub_x(pt, vdd_y, "vdd", foreign)
            body += _draw_rail_riser_svg(pt, vdd_y, "vdd", stub_x)

    gnd_pts = _gnd_points(placed)
    if gnd_pts:
        body += f'<line x1="{margin}" y1="{gnd_y}" x2="{width - margin}" y2="{gnd_y}" {_RAIL_CLASS}/>\n'
        body += f'<text x="{margin}" y="{gnd_y + 16}" {_DIM}>GND</text>\n'
        for pt in gnd_pts:
            stub_x = _rail_riser_stub_x(pt, gnd_y, "0", foreign)
            body += _draw_rail_riser_svg(pt, gnd_y, "0", stub_x)

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
        for node, _, pt in terminal_refs(pd.dev, pd.origin, mirror=pd.mirror):
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
    is_opamp = "opamp" in topo
    left_lbl = "IN-" if is_opamp else "IN+"
    right_lbl = "IN+" if is_opamp else "IN-"

    if "vinp" in io:
        g = io["vinp"]
        labels += f'<text x="50" y="{g.y + 4}" {_DIM}>{left_lbl}</text>\n'
        labels += (
            f'<line x1="70" y1="{g.y}" x2="{g.x}" y2="{g.y}" class="signal-wire io-stub"/>\n'
        )
    if "vinn" in io:
        g = io["vinn"]
        ext_x = max(width - 70, g.x + 40)
        labels += f'<text x="{ext_x + 8}" y="{g.y + 4}" {_DIM}>{right_lbl}</text>\n'
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
    topo = topology.lower()

    variant = "default"
    if topo == "two_stage_miller_opamp":
        variant, crossing_score, placed = _choose_opamp_variant(devices, topology)
        floorplan_defined = True
    else:
        layout_map, floorplan_defined = _resolve_layout(devices, topology, device_meta)
        placed = _place_devices(devices, layout_map, floorplan_defined=floorplan_defined)
        crossing_score = -1

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
        variant=variant,
        crossing_score=crossing_score,
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
    all_junctions = routed.junctions
    body += segments_to_svg_lines(
        routed.segments, _WIRE_CLASS, _RAIL_CLASS, junctions=all_junctions
    )

    nets = _collect_net_points(layout.placed)
    body += _draw_rails(layout.placed, nets, layout.width, layout.height, routed.segments)
    body += _pin_labels(layout.placed, layout.topology, layout.width)

    for j in all_junctions:
        body += f'<circle cx="{j.x}" cy="{j.y}" r="3" {_DOT}/>\n'

    title = layout.topology or "circuit"
    head = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {layout.width} {layout.height}" width="{layout.width}" height="{layout.height}">
{_SVG_STYLES}
<text x="20" y="22" {_TITLE}>{title} · {layout.title_suffix}</text>
"""
    return head + body + "</svg>"
