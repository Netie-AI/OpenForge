"""Role-based schematic floorplans, placement, and orthogonal wire routing.

CHANGES vs. the version that shipped the tangled two_stage_miller_opamp
render (see chat / docs/schematic-layout-skill.md for the full writeup):

1. `route_all_nets` now returns structured `Segment` objects
   (schematic_geometry) instead of only SVG strings. Nets whose tap points
   span more than `_WIDE_SPAN_THRESHOLD` px are bus-routed instead of
   "centroid star" routed. A star route from one point on the far side of
   the canvas draws a long arm straight across everything in between; a
   bus route picks a spine and taps into it, like a real schematic does
   for shared bias/rail nets. Critically, the spine position for ALL wide
   nets is chosen jointly (one combinatorial search, not net-by-net) —
   net-by-net greedy selection lets whichever net is routed first claim
   the cheapest position regardless of what it blocks afterward; this was
   verified to fail in practice (see docs/schematic-layout-skill.md).

2. `build_schematic_layout` no longer hardcodes where M6/M7 go for
   `two_stage_miller_opamp`. It generates a small set of named placement
   variants (`_STAGE2_VARIANTS`), scores each with
   `schematic_geometry.score_layout`, and keeps the lowest-scoring one. The
   chosen variant and its score are logged — this is meant to be a
   reviewable decision, not a silent pick.

3. `tests/test_schematic_no_tangling.py` (separate file) asserts the chosen
   variant's score is 0 and stays 0 — this is the CI gate against future
   regressions of this exact bug.

INTEGRATION NOTE (read before merging): `_DEVICE_BBOX` / `_CAP_BBOX` below
are approximate — back-derived from the sample SVG, not read out of
`symbols.py`. If `symbols.render_symbol` exposes (or can be made to expose)
the real local-coordinate bounding box, swap it in; until then the
wire-through-device check is best-effort, not exact.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from openanalog.eda.netlist_graph import SpiceDevice
from openanalog.eda.schematic_geometry import (
    DeviceBox,
    Segment,
    find_bad_crossings,
    score_layout,
)
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

# Net point-cloud span (px) beyond which we bus-route instead of star-route.
# Below this, a centroid star still reads cleanly and is more compact.
_WIDE_SPAN_THRESHOLD = 150

# Approximate symbol footprint in local (pre-translate) coordinates, used
# only for the wire-through-device check. See INTEGRATION NOTE above.
_DEVICE_BBOX = (0, 0, 36, 40)
_CAP_BBOX = (0, 0, 54, 48)

# Topology names with defined floorplans.
_FLOORPLAN_TOPOLOGIES = frozenset({"two_stage_miller_opamp", "diff_pair_comparator"})

# Shared diff-pair floorplan base (op-amp + comparator). M6/M7 are NOT here
# any more — they're decided per-topology by the variant search below, since
# they're the devices whose nets actually span the floorplan.
_DIFF_PAIR_LAYOUT_BASE: dict[str, tuple[str, int, bool]] = {
    "M3": ("load", 0, False),
    "M4": ("load", 1, True),
    "M1": ("input", 0, False),
    "M2": ("input", 1, True),
    "M5": ("tail", 0, False),
    "M8": ("bias", 0, False),
    "Iref": ("bias", 1, False),
    "Cc": ("miller", 0, False),
    "Rload": ("output", 2, False),
}

# Comparator floorplan keeps M6/M7 as plain output-stage devices — it has no
# Miller-compensated second stage, so the original placement is fine as-is.
_COMPARATOR_STAGE2 = {"M6": ("output", 0, False), "M7": ("output", 1, False)}

# Two named placements for the op-amp's stage-2 devices. The search in
# build_schematic_layout() scores both against the real netlist and keeps
# whichever has fewer bad crossings — this list is meant to grow, not to be
# the final word on layout aesthetics.
_STAGE2_VARIANTS: dict[str, dict[str, tuple[str, int, bool]]] = {
    # Original behavior: stage 2 isolated in its own column on the far
    # right. Kept as a variant (not deleted) so the search has a baseline
    # to beat, and so a future topology where this genuinely is better
    # doesn't need new code.
    "isolated": {"M6": ("output", 0, False), "M7": ("output", 1, False)},
    # M7's gate is the bias net (nb) — the same net as M5's gate and M8's
    # gate/drain. Placing M7 in M5's column turns that net from a
    # cross-canvas run into one short local bus.
    "tail_aligned": {"M6": ("output", 0, False), "M7": ("tail", 1, False)},
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
    variant: str = "default"
    crossing_score: int = 0


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
    """Used for diff_pair_comparator and any non-search-driven floorplan path."""
    topo = (topology or "").lower()
    if topo == "diff_pair_comparator":
        layout = {k.upper(): v for k, v in {**_DIFF_PAIR_LAYOUT_BASE, **_COMPARATOR_STAGE2}.items()}
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


def _manhattan(a: Point, b: Point) -> list[tuple[int, int, int, int]]:
    if a.x == b.x or a.y == b.y:
        return [(a.x, a.y, b.x, b.y)]
    mid = Point(b.x, a.y)
    return [(a.x, a.y, mid.x, mid.y), (mid.x, mid.y, b.x, b.y)]


def _route_local(points: list[Point], net: str) -> tuple[list[Segment], set[Point]]:
    """Star routing for spatially-close nets (2-3 nearby pins)."""
    if len(points) == 2:
        segs = [Segment(x1, y1, x2, y2, net=net) for x1, y1, x2, y2 in _manhattan(points[0], points[1])]
        return segs, set()

    jx = snap(sum(p.x for p in points) // len(points))
    jy = snap(sum(p.y for p in points) // len(points))
    junction = Point(jx, jy)
    segs: list[Segment] = []
    for pt in points:
        for x1, y1, x2, y2 in _manhattan(pt, junction):
            segs.append(Segment(x1, y1, x2, y2, net=net))
    return segs, {junction}


def _spine_candidates(points: list[Point]) -> list[int]:
    return sorted({p.x for p in points})


def _build_spine(points: list[Point], net: str, spine_x: int) -> tuple[list[Segment], set[Point], int]:
    """Bus segments for one net at a *given* spine x, plus total stub reach
    (used as a tiebreaker — see route_all_nets)."""
    ys = [p.y for p in points]
    segs = [Segment(spine_x, min(ys), spine_x, max(ys), net=net, kind="stub")]
    junctions: set[Point] = set()
    reach = 0
    for pt in points:
        if pt.x != spine_x:
            segs.append(Segment(pt.x, pt.y, spine_x, pt.y, net=net, kind="stub"))
            reach += abs(pt.x - spine_x)
        junctions.add(Point(spine_x, pt.y))
    return segs, junctions, reach


def _segments_to_svg(segments: list[Segment]) -> str:
    out = []
    for s in segments:
        cls = _RAIL_CLASS if s.kind == "rail" else _WIRE_CLASS
        out.append(f'<line x1="{s.x1}" y1="{s.y1}" x2="{s.x2}" y2="{s.y2}" {cls}/>')
    return ("\n".join(out) + "\n") if out else ""


def _device_boxes(placed: list[PlacedDevice]) -> list[DeviceBox]:
    boxes = []
    for pd in placed:
        is_cap = pd.dev.kind == "C"
        bx0, by0, bx1, by1 = _CAP_BBOX if is_cap else _DEVICE_BBOX
        nets = frozenset(n.lower() for n in terminal_positions(pd.dev, pd.origin, mirror=pd.mirror).keys())
        boxes.append(
            DeviceBox(
                name=pd.dev.name,
                x=pd.origin.x + bx0,
                y=pd.origin.y + by0,
                w=bx1 - bx0,
                h=by1 - by0,
                terminal_nets=nets,
            )
        )
    return boxes


# Hard ceiling on the joint spine search so a pathological circuit (many
# wide-spanning nets, each with many distinct tap x's) can't blow up
# rendering time. 4 wide nets x 4 candidates = 256 combinations is already
# generous for anything in the current topology library; if this ever
# trips, that's a sign the floorplan needs a real placement redesign, not a
# bigger search budget.
_MAX_JOINT_COMBINATIONS = 512


def route_all_nets(placed: list[PlacedDevice]) -> tuple[list[Segment], set[Point]]:
    """Structured routing for every signal net (rails excluded — see module
    docstring point (1) limitation). Shared by scoring and rendering so they
    can never drift out of sync with each other.

    Nets with >=3 tap points spanning more than `_WIDE_SPAN_THRESHOLD` px
    are bus-routed; everything else is star-routed. Local (star) nets are
    routed first and held fixed. Wide nets are then searched *jointly*:
    every combination of {candidate spine x per wide net} is scored
    together against the fixed nets, and the lowest-scoring combination
    wins. This matters — a greedy one-net-at-a-time search lets whichever
    net goes first claim the cheapest position regardless of what it
    blocks for the nets that come after it (verified to fail in practice;
    see docs/schematic-layout-skill.md).
    """
    nets = _collect_net_points(placed)
    rail_names = {"vdd", "vdd3", "0"}

    def _dedupe(points: list[Point]) -> list[Point]:
        seen: set[tuple[int, int]] = set()
        out: list[Point] = []
        for p in points:
            key = (p.x, p.y)
            if key not in seen:
                seen.add(key)
                out.append(p)
        return out

    def _span(points: list[Point]) -> int:
        xs = [p.x for p in points]
        ys = [p.y for p in points]
        return max(max(xs) - min(xs), max(ys) - min(ys))

    wide_nets: list[tuple[str, list[Point]]] = []
    local_nets: list[tuple[str, list[Point]]] = []
    for net_name, points in nets.items():
        if net_name in rail_names:
            continue
        unique = _dedupe(points)
        if len(unique) < 2:
            continue
        if len(unique) >= 3 and _span(unique) > _WIDE_SPAN_THRESHOLD:
            wide_nets.append((net_name, unique))
        else:
            local_nets.append((net_name, unique))

    fixed_segments: list[Segment] = []
    fixed_junctions: set[Point] = set()
    for net_name, unique in local_nets:
        segs, junctions = _route_local(unique, net_name)
        fixed_segments += segs
        if len(unique) >= 3:
            fixed_junctions |= junctions

    if not wide_nets:
        return fixed_segments, fixed_junctions

    candidate_lists = [_spine_candidates(points) for _, points in wide_nets]
    n_combos = 1
    for c in candidate_lists:
        n_combos *= max(len(c), 1)
    if n_combos > _MAX_JOINT_COMBINATIONS:
        log.warning(
            "schematic routing: %d wide-span nets produce %d spine combinations "
            "(> %d cap) — falling back to per-net median placement, crossing "
            "score for this render is not guaranteed minimal",
            len(wide_nets), n_combos, _MAX_JOINT_COMBINATIONS,
        )
        segs_all: list[Segment] = []
        junc_all: set[Point] = set()
        for (net_name, points), cands in zip(wide_nets, candidate_lists):
            spine_x = cands[len(cands) // 2]
            segs, junctions, _reach = _build_spine(points, net_name, spine_x)
            segs_all += segs
            junc_all |= junctions
        return fixed_segments + segs_all, fixed_junctions | junc_all

    import itertools

    best: tuple[int, int, list[Segment], set[Point]] | None = None
    for combo in itertools.product(*candidate_lists):
        combo_segments: list[Segment] = []
        combo_junctions: set[Point] = set()
        total_reach = 0
        for (net_name, points), spine_x in zip(wide_nets, combo):
            segs, junctions, reach = _build_spine(points, net_name, spine_x)
            combo_segments += segs
            combo_junctions |= junctions
            total_reach += reach

        all_segments = fixed_segments + combo_segments
        all_junction_keys = {(j.x, j.y) for j in (fixed_junctions | combo_junctions)}
        score = len(find_bad_crossings(all_segments, all_junction_keys))
        key = (score, total_reach)
        if best is None or key < best[:2]:
            best = (score, total_reach, combo_segments, combo_junctions)

    assert best is not None
    _, _, combo_segments, combo_junctions = best
    return fixed_segments + combo_segments, fixed_junctions | combo_junctions


def _score_placement(devices: list[SpiceDevice], layout_map: dict[str, tuple[str, int, bool]]) -> tuple[int, list[PlacedDevice]]:
    placed = _place_devices(devices, layout_map, floorplan_defined=True)
    segments, junctions = route_all_nets(placed)
    boxes = _device_boxes(placed)
    junction_keys = {(j.x, j.y) for j in junctions}
    score = score_layout(segments, junction_keys, boxes)
    return score, placed


def _choose_opamp_placement(devices: list[SpiceDevice]) -> tuple[str, int, list[PlacedDevice]]:
    results: list[tuple[int, str, list[PlacedDevice]]] = []
    for variant_name, stage2 in _STAGE2_VARIANTS.items():
        layout_map = {k.upper(): v for k, v in {**_DIFF_PAIR_LAYOUT_BASE, **stage2}.items()}
        score, placed = _score_placement(devices, layout_map)
        log.info("schematic floorplan variant=%s crossing_score=%d", variant_name, score)
        results.append((score, variant_name, placed))

    results.sort(key=lambda r: r[0])
    best_score, best_variant, best_placed = results[0]
    log.info(
        "schematic floorplan: chose variant=%s (crossing_score=%d, %d variant(s) evaluated)",
        best_variant, best_score, len(results),
    )
    return best_variant, best_score, best_placed


def _draw_miller_cap(dev: SpiceDevice, origin: Point) -> str:
    ox, oy = origin.x, origin.y
    return (
        f'<line x1="{ox}" y1="{oy}" x2="{ox + 20}" y2="{oy + 30}" stroke="#ffcc66" stroke-width="1.5"/>\n'
        f'<line x1="{ox + 24}" y1="{oy + 26}" x2="{ox + 24}" y2="{oy + 34}" stroke="#ffcc66" stroke-width="2"/>\n'
        f'<line x1="{ox + 30}" y1="{oy + 26}" x2="{ox + 30}" y2="{oy + 34}" stroke="#ffcc66" stroke-width="2"/>\n'
        f'<line x1="{ox + 34}" y1="{oy + 30}" x2="{ox + 54}" y2="{oy}" stroke="#ffcc66" stroke-width="1.5"/>\n'
        f'<text x="{ox + 8}" y="{oy + 48}" {_MILLER}>{dev.name}</text>\n'
    )


def _vdd_nodes(placed: list[PlacedDevice]) -> list[Point]:
    pts: list[Point] = []
    for pd in placed:
        for node, pt in terminal_positions(pd.dev, pd.origin, mirror=pd.mirror).items():
            if node.lower() in ("vdd", "vdd3"):
                pts.append(pt)
    return pts


def _gnd_points(placed: list[PlacedDevice]) -> list[Point]:
    pts: list[Point] = []
    for pd in placed:
        tmap = terminal_positions(pd.dev, pd.origin, mirror=pd.mirror)
        for node, pt in tmap.items():
            if node == "0":
                pts.append(pt)
    return pts


def _draw_rails(placed: list[PlacedDevice], width: int, height: int) -> str:
    body = ""
    margin = 40
    vdd_y = snap(50)
    gnd_y = snap(height - 40)

    vdd_pts = _vdd_nodes(placed)
    if vdd_pts:
        body += f'<line x1="{margin}" y1="{vdd_y}" x2="{width - margin}" y2="{vdd_y}" {_RAIL_CLASS}/>\n'
        body += f'<text x="{margin}" y="{vdd_y - 8}" {_VDD_LABEL}>VDD</text>\n'
        for pt in vdd_pts:
            body += f'<line x1="{pt.x}" y1="{vdd_y}" x2="{pt.x}" y2="{pt.y}" {_WIRE_CLASS}/>\n'

    gnd_pts = _gnd_points(placed)
    if gnd_pts:
        body += f'<line x1="{margin}" y1="{gnd_y}" x2="{width - margin}" y2="{gnd_y}" {_RAIL_CLASS}/>\n'
        body += f'<text x="{margin}" y="{gnd_y + 16}" {_DIM}>GND</text>\n'
        for pt in gnd_pts:
            body += f'<line x1="{pt.x}" y1="{pt.y}" x2="{pt.x}" y2="{gnd_y}" {_WIRE_CLASS}/>\n'

    return body


def _io_terminals(placed: list[PlacedDevice]) -> dict[str, Point]:
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
        labels += f'<line x1="70" y1="{g.y}" x2="{g.x}" y2="{g.y}" class="signal-wire io-stub"/>\n'
    if "vinn" in io:
        g = io["vinn"]
        ext_x = max(width - 70, g.x + 40)
        labels += f'<text x="{ext_x + 8}" y="{g.y + 4}" {_DIM}>IN-</text>\n'
        labels += f'<line x1="{ext_x}" y1="{g.y}" x2="{g.x}" y2="{g.y}" class="signal-wire io-stub"/>\n'
    if "vout" in io:
        g = io["vout"]
        ext_x = max(width - 70, g.x + 20)
        labels += f'<text x="{ext_x + 10}" y="{g.y + 4}" {_DIM}>OUT</text>\n'
        labels += f'<line x1="{ext_x}" y1="{g.y}" x2="{g.x}" y2="{g.y}" class="signal-wire io-stub"/>\n'
    return labels


def build_schematic_layout(
    devices: list[SpiceDevice],
    result: dict[str, Any] | None = None,
) -> SchematicLayout:
    result = result or {}
    topology = str(result.get("topology") or result.get("category") or "")
    device_meta = result.get("devices") or []
    topo = topology.lower()

    if topo == "two_stage_miller_opamp":
        variant, score, placed = _choose_opamp_placement(devices)
        floorplan_defined = True
    else:
        layout_map, floorplan_defined = _resolve_layout(devices, topology, device_meta)
        placed = _place_devices(devices, layout_map, floorplan_defined=floorplan_defined)
        if floorplan_defined:
            _, junctions = route_all_nets(placed)
            boxes = _device_boxes(placed)
            segments, _ = route_all_nets(placed)
            score = score_layout(segments, {(j.x, j.y) for j in junctions}, boxes)
        else:
            score = -1  # not scored: no floorplan to score against
        variant = "default"

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
        crossing_score=score,
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

    segments, junctions = route_all_nets(layout.placed)
    body += _segments_to_svg(segments)
    body += _draw_rails(layout.placed, layout.width, layout.height)
    body += _pin_labels(layout.placed, layout.topology, layout.width)

    for j in junctions:
        body += f'<circle cx="{j.x}" cy="{j.y}" r="3" {_DOT}/>\n'

    title = layout.topology or "circuit"
    if layout.crossing_score > 0:
        log.warning(
            "%s schematic rendered with crossing_score=%d (variant=%s) — see "
            "tests/test_schematic_no_tangling.py",
            title, layout.crossing_score, layout.variant,
        )
    head = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {layout.width} {layout.height}" width="{layout.width}" height="{layout.height}">
{_SVG_STYLES}
<text x="20" y="22" {_TITLE}>{title} · {layout.title_suffix}</text>
"""
    return head + body + "</svg>"
