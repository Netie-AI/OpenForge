"""Schematic connectivity verification — terminal/wire match and netlist equivalence."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from openanalog.eda.netlist_graph import SpiceDevice
from openanalog.eda.schematic_layout import (
    PlacedDevice,
    _FLOORPLAN_TOPOLOGIES,
    _gnd_points,
    _vdd_nodes,
    all_rail_riser_segments,
    build_schematic_layout,
    render_schematic_svg,
)
from openanalog.eda.schematic_router import STUB_LEN, route_nets, terminal_stub
from openanalog.eda.symbols import Point, terminal_refs

_LINE_RE = re.compile(
    r'<line x1="(-?\d+)" y1="(-?\d+)" x2="(-?\d+)" y2="(-?\d+)"([^/]*)/>'
)
_CIRCLE_RE = re.compile(r'<circle cx="(-?\d+)" cy="(-?\d+)" r="(\d+)"')
_PATH_HOP_RE = re.compile(
    r'<path d="M (-?\d+) (-?\d+) A (\d+) (\d+) 0 0 1 (-?\d+) (-?\d+)"[^>]*wire-hop'
)
_EPSILON = 0.5


def _pt_key(p: Point) -> tuple[int, int]:
    return (p.x, p.y)


def _near(a: Point, b: Point, eps: float = _EPSILON) -> bool:
    return abs(a.x - b.x) <= eps and abs(a.y - b.y) <= eps


def _point_on_segment(x: int, y: int, x1: int, y1: int, x2: int, y2: int) -> bool:
    if x1 == x2 == x:
        return min(y1, y2) - _EPSILON <= y <= max(y1, y2) + _EPSILON
    if y1 == y2 == y:
        return min(x1, x2) - _EPSILON <= x <= max(x1, x2) + _EPSILON
    return (abs(x - x1) <= _EPSILON and abs(y - y1) <= _EPSILON) or (
        abs(x - x2) <= _EPSILON and abs(y - y2) <= _EPSILON
    )


def parse_wire_segments(svg: str) -> list[tuple[int, int, int, int, bool]]:
    """Return (x1, y1, x2, y2, is_io_stub) for routed schematic wires only."""
    segments: list[tuple[int, int, int, int, bool]] = []
    for m in _LINE_RE.finditer(svg):
        attrs = m.group(5)
        if "signal-wire" not in attrs:
            continue
        x1, y1, x2, y2 = (int(m.group(i)) for i in range(1, 5))
        segments.append((x1, y1, x2, y2, "io-stub" in attrs))
    for m in _PATH_HOP_RE.finditer(svg):
        x1, y1, x2, y2 = int(m.group(1)), int(m.group(2)), int(m.group(5)), int(m.group(6))
        segments.append((x1, y1, x2, y2, False))
    return segments


def parse_terminal_stub_segments(svg: str) -> list[tuple[int, int, int, int]]:
    """Return device terminal stub segments (Phase 0.8)."""
    stubs: list[tuple[int, int, int, int]] = []
    for m in _LINE_RE.finditer(svg):
        attrs = m.group(5)
        if "terminal-stub" not in attrs:
            continue
        stubs.append(tuple(int(m.group(i)) for i in range(1, 5)))  # type: ignore[misc]
    return stubs


def junction_points(svg: str) -> set[tuple[int, int]]:
    pts: set[tuple[int, int]] = set()
    for m in _CIRCLE_RE.finditer(svg):
        if int(m.group(3)) == 3:
            pts.add((int(m.group(1)), int(m.group(2))))
    return pts


def hop_centers(svg: str) -> set[tuple[int, int]]:
    """Centers of wire-hop arcs (unconnected crossing notation)."""
    centers: set[tuple[int, int]] = set()
    for m in _PATH_HOP_RE.finditer(svg):
        x1, y1, x2, y2 = int(m.group(1)), int(m.group(2)), int(m.group(5)), int(m.group(6))
        centers.add(((x1 + x2) // 2, (y1 + y2) // 2))
    return centers


def required_junction_points(devices: list[SpiceDevice], result: dict[str, Any]) -> set[tuple[int, int]]:
    """Electrical junction dots required by routing (3+ arms per net, incl. interior taps)."""
    layout = build_schematic_layout(devices, result)
    routed = route_nets(layout.placed)
    return {(p.x, p.y) for p in routed.junctions}


def required_hop_centers(devices: list[SpiceDevice], result: dict[str, Any]) -> set[tuple[int, int]]:
    """Crossing centers where an unrelated-net hop must appear."""
    from openanalog.eda.schematic_router import _hop_points_by_segment

    layout = build_schematic_layout(devices, result)
    routed = route_nets(layout.placed)
    centers: set[tuple[int, int]] = set()
    hop_map = _hop_points_by_segment(routed.segments, routed.junctions)
    for points in hop_map.values():
        centers.update(points)
    return centers


def collinear_net_overlap_errors(devices: list[SpiceDevice], result: dict[str, Any]) -> list[str]:
    """Two distinct nets must not share a collinear wire track (H or V, incl. rail risers).

    Terminal stubs are excluded — they are short pin escapes, not routed backbone tracks.
    """
    from openanalog.eda.schematic_geometry import Segment, find_collinear_overlaps

    layout = build_schematic_layout(devices, result)
    routed = route_nets(layout.placed)
    geom = [
        Segment(s.x1, s.y1, s.x2, s.y2, s.net, s.kind)
        for s in routed.segments
        if s.kind == "wire"
    ]
    nets = _collect_net_points(layout.placed)
    geom.extend(
        all_rail_riser_segments(layout.placed, nets, layout.height, routed.segments)
    )
    errors: list[str] = []
    for a, b, hit in find_collinear_overlaps(geom):
        axis, coord, lo, hi = hit
        if axis == 0:
            errors.append(
                f"collinear overlap y={coord} x[{lo},{hi}]: nets {a.net!r} vs {b.net!r}"
            )
        else:
            errors.append(
                f"collinear overlap x={coord} y[{lo},{hi}]: nets {a.net!r} vs {b.net!r}"
            )
    return errors


def false_junction_dot_errors(devices: list[SpiceDevice], result: dict[str, Any]) -> list[str]:
    """Junction dots must not sit on a foreign net's track."""
    from openanalog.eda.schematic_router import _is_segment_endpoint, _is_segment_interior

    svg = render_schematic_svg(devices, result)
    dots = junction_points(svg)
    layout = build_schematic_layout(devices, result)
    routed = route_nets(layout.placed)
    sig = [s for s in routed.segments if s.kind in ("wire", "stub")]
    errors: list[str] = []
    for x, y in dots:
        nets: set[str] = set()
        for seg in sig:
            if _is_segment_endpoint(x, y, seg) or _is_segment_interior(x, y, seg):
                nets.add(seg.net)
        if len(nets) > 1:
            errors.append(
                f"junction dot at ({x}, {y}) touches multiple nets {sorted(nets)} (false short)"
            )
    return errors


def terminal_map(placed: list[PlacedDevice]) -> dict[tuple[int, int], list[tuple[str, str]]]:
    mapping: dict[tuple[int, int], list[tuple[str, str]]] = {}
    for pd in placed:
        for node, pin, pt in terminal_refs(pd.dev, pd.origin, mirror=pd.mirror):
            key = _pt_key(pt)
            mapping.setdefault(key, []).append((f"{pd.dev.name.upper()}.{pin}", node.lower()))
    return mapping


def netlist_adjacency(devices: list[SpiceDevice]) -> dict[str, set[tuple[str, str]]]:
    adj: dict[str, set[tuple[str, str]]] = {}
    for dev in devices:
        if dev.kind == "M":
            pin_names = ("d", "g", "s")
            for pin, node in zip(pin_names, dev.nodes[:3], strict=False):
                adj.setdefault(node.lower(), set()).add((f"{dev.name.upper()}.{pin}", node.lower()))
            continue
        pin_names = ("p", "n")
        for pin, node in zip(pin_names, dev.nodes[:2], strict=False):
            adj.setdefault(node.lower(), set()).add((f"{dev.name.upper()}.{pin}", node.lower()))
    return adj


def _wire_adjacency(
    segments: list[tuple[int, int, int, int, bool]],
) -> dict[tuple[int, int], set[tuple[int, int]]]:
    """Grid points connected by Manhattan wire segments."""
    adj: dict[tuple[int, int], set[tuple[int, int]]] = defaultdict(set)

    def add_edge(a: tuple[int, int], b: tuple[int, int]) -> None:
        adj[a].add(b)
        adj[b].add(a)

    for x1, y1, x2, y2, is_io in segments:
        if is_io:
            continue
        if x1 == x2:
            y0, y1r = sorted((y1, y2))
            for y in range(y0, y1r):
                add_edge((x1, y), (x1, y + 1))
        elif y1 == y2:
            x0, x1r = sorted((x1, x2))
            for x in range(x0, x1r):
                add_edge((x, y1), (x + 1, y1))
        else:
            add_edge((x1, y1), (x2, y2))
    return adj


def _connected_component(
    start: tuple[int, int],
    wire_adj: dict[tuple[int, int], set[tuple[int, int]]],
) -> set[tuple[int, int]]:
    seen = {start}
    stack = [start]
    while stack:
        cur = stack.pop()
        for nxt in wire_adj.get(cur, ()):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen


def _terminal_on_segment(
    pt: tuple[int, int],
    segments: list[tuple[int, int, int, int, bool]],
    *,
    io_only: bool = False,
    signal_only: bool = False,
) -> bool:
    x, y = pt
    for x1, y1, x2, y2, is_io in segments:
        if io_only and not is_io:
            continue
        if signal_only and is_io:
            continue
        if _point_on_segment(x, y, x1, y1, x2, y2):
            return True
    return False


def _terminal_on_wire(
    pt: tuple[int, int],
    segments: list[tuple[int, int, int, int, bool]],
) -> bool:
    return _terminal_on_segment(pt, segments, signal_only=True)


def _io_terminal_targets(placed: list[PlacedDevice]) -> dict[str, tuple[int, int]]:
    """External nets and the schematic terminal each IO stub must reach."""
    targets: dict[str, tuple[int, int]] = {}
    for pd in placed:
        for node, _, pt in terminal_refs(pd.dev, pd.origin, mirror=pd.mirror):
            nl = node.lower()
            if nl in ("vinp", "vinn"):
                targets[nl] = _pt_key(pt)
            elif nl == "vout" and (nl not in targets or pd.dev.kind == "M"):
                targets[nl] = _pt_key(pt)
    return targets


def _verify_io_stubs(
    placed: list[PlacedDevice],
    segments: list[tuple[int, int, int, int, bool]],
) -> list[str]:
    """IO stub segments must reach their device terminals (external end may dangle)."""
    errors: list[str] = []
    io_segments = [s for s in segments if s[4]]
    if not io_segments:
        errors.append("no io-stub segments found in schematic SVG")
        return errors

    targets = _io_terminal_targets(placed)
    label_map = {"vinp": "IN+", "vinn": "IN-", "vout": "OUT"}
    for net, pt in targets.items():
        if not _terminal_on_segment(pt, io_segments, io_only=True):
            label = label_map.get(net, net)
            errors.append(
                f"io stub for {label} ({net}) does not reach terminal at ({pt[0]}, {pt[1]})"
            )

    terminal_pts = set(targets.values())
    for x1, y1, x2, y2, _ in io_segments:
        for x, y in ((x1, y1), (x2, y2)):
            if (x, y) in terminal_pts:
                continue
            if _terminal_on_segment((x, y), segments, signal_only=True):
                continue
            # External pin end — allowed to dangle.
    return errors


def _is_passive_bridge(dev: SpiceDevice) -> bool:
    return dev.kind in ("C", "R") and len(dev.nodes) == 2


def _verify_render_geometry(placed: list[PlacedDevice]) -> list[str]:
    """Render-path assertion: Manhattan wires + passive stubs terminate on named nets."""
    errors: list[str] = []
    routed = route_nets(placed)

    for seg in routed.segments:
        if seg.kind != "wire":
            continue
        if seg.x1 != seg.x2 and seg.y1 != seg.y2:
            errors.append(
                f"non-axis signal segment on net {seg.net}: ({seg.x1},{seg.y1})->({seg.x2},{seg.y2})"
            )

    for pd in placed:
        if not _is_passive_bridge(pd.dev):
            continue
        for node, pin, pt in terminal_refs(pd.dev, pd.origin, mirror=pd.mirror):
            nl = node.lower()
            if nl in {"0", "vdd", "vdd3"}:
                continue
            stub = terminal_stub(pd.dev, pd.origin, node, mirror=pd.mirror, pin=pin, terminal=pt)
            sx, sy = stub.stub_end.x, stub.stub_end.y
            attached = any(
                seg.kind == "wire"
                and seg.net == nl
                and _point_on_segment(sx, sy, seg.x1, seg.y1, seg.x2, seg.y2)
                for seg in routed.segments
            )
            if not attached:
                errors.append(
                    f"passive stub {pd.dev.name}.{node} ends at ({sx},{sy}) without named-net tap ({nl})"
                )

    return errors


def _rail_endpoints(
    placed: list[PlacedDevice],
    nets: dict[str, list[Point]],
    width: int,
    height: int,
    routed_segments: list | None = None,
) -> set[tuple[int, int]]:
    margin = 40
    vdd_y = round(50 / 10) * 10
    gnd_y = round((height - 40) / 10) * 10
    pts: set[tuple[int, int]] = set()
    for x in range(margin, width - margin + 1, 10):
        pts.add((x, vdd_y))
        pts.add((x, gnd_y))
    if routed_segments is not None:
        for seg in all_rail_riser_segments(placed, nets, height, routed_segments):
            x1, y1, x2, y2 = seg.x1, seg.y1, seg.x2, seg.y2
            if x1 == x2:
                for y in range(min(y1, y2), max(y1, y2) + 1):
                    pts.add((x1, y))
            elif y1 == y2:
                for x in range(min(x1, x2), max(x1, x2) + 1):
                    pts.add((x, y1))
        for pt in _vdd_nodes(nets):
            pts.add(_pt_key(pt))
        for pt in _gnd_points(placed):
            pts.add(_pt_key(pt))
        return pts

    for pt in _vdd_nodes(nets):
        stub_x = pt.x
        for y in range(min(vdd_y, pt.y), max(vdd_y, pt.y) + 1):
            pts.add((stub_x, y))
        pts.add(_pt_key(pt))

    for pt in _gnd_points(placed):
        stub_x = pt.x
        for y in range(min(pt.y, gnd_y), max(pt.y, gnd_y) + 1):
            pts.add((stub_x, y))
        pts.add(_pt_key(pt))
    return pts


def _allowed_dangling_points(
    placed: list[PlacedDevice],
    nets: dict[str, list[Point]],
    width: int,
    height: int,
    svg: str,
) -> set[tuple[int, int]]:
    allowed: set[tuple[int, int]] = set()
    for pd in placed:
        for node, pin, pt in terminal_refs(pd.dev, pd.origin, mirror=pd.mirror):
            allowed.add(_pt_key(pt))
            if node != "0" and node.lower() not in ("vdd", "vdd3"):
                stub = terminal_stub(pd.dev, pd.origin, node, mirror=pd.mirror, pin=pin, terminal=pt)
                allowed.add(_pt_key(stub.stub_end))
    allowed |= junction_points(svg)
    allowed |= _rail_endpoints(placed, nets, width, height)
    return allowed


def _collect_net_points(placed: list[PlacedDevice]) -> dict[str, list[Point]]:
    nets: dict[str, list[Point]] = {}
    for pd in placed:
        for node, _, pt in terminal_refs(pd.dev, pd.origin, mirror=pd.mirror):
            if node == "0":
                continue
            nets.setdefault(node.lower(), []).append(pt)
    return nets


def schematic_adjacency_from_wires(
    placed: list[PlacedDevice],
    segments: list[tuple[int, int, int, int, bool]],
) -> dict[str, set[tuple[str, str]]]:
    """Map netlist node names to pins connected by the wire graph."""
    tmap = terminal_map(placed)
    wire_adj = _wire_adjacency(segments)
    adj: dict[str, set[tuple[str, str]]] = {}

    visited: set[tuple[int, int]] = set()
    for pt, pins in tmap.items():
        if pt in visited:
            continue
        component = _connected_component(pt, wire_adj)
        visited |= component
        nets_in_comp: set[str] = set()
        pins_in_comp: set[tuple[str, str]] = set()
        for cpt in component:
            for pin in tmap.get(cpt, ()):
                nets_in_comp.add(pin[1])
                pins_in_comp.add(pin)
        if len(nets_in_comp) == 1:
            net = next(iter(nets_in_comp))
            adj.setdefault(net, set()).update(pins_in_comp)
        else:
            for pin in pins_in_comp:
                adj.setdefault(pin[1], set()).add(pin)
    return adj


def _segments_cross(
    a: tuple[int, int, int, int, bool],
    b: tuple[int, int, int, int, bool],
) -> tuple[int, int] | None:
    ax1, ay1, ax2, ay2, aio = a
    bx1, by1, bx2, by2, bio = b
    if aio or bio:
        return None
    shared = {(ax1, ay1), (ax2, ay2)} & {(bx1, by1), (bx2, by2)}
    if shared:
        return None
    if ax1 == ax2 and by1 == by2:
        x, y = ax1, by1
        ay_lo, ay_hi = sorted((ay1, ay2))
        bx_lo, bx_hi = sorted((bx1, bx2))
        if bx_lo < x < bx_hi and ay_lo < y < ay_hi:
            return (x, y)
    if ay1 == ay2 and bx1 == bx2:
        x, y = bx1, ay1
        ax_lo, ax_hi = sorted((ax1, ax2))
        by_lo, by_hi = sorted((by1, by2))
        if ax_lo < x < ax_hi and by_lo < y < by_hi:
            return (x, y)
    return None


def _segment_nets(
    seg: tuple[int, int, int, int, bool],
    tmap: dict[tuple[int, int], list[tuple[str, str]]],
) -> set[str]:
    x1, y1, x2, y2, _ = seg
    nets: set[str] = set()
    for (tx, ty), pins in tmap.items():
        if _point_on_segment(tx, ty, x1, y1, x2, y2):
            for _, node in pins:
                nets.add(node)
    return nets


def _false_junction_at_crossings(
    segments: list[tuple[int, int, int, int, bool]],
    tmap: dict[tuple[int, int], list[tuple[str, str]]],
    junctions: set[tuple[int, int]],
) -> list[str]:
    """Junction dots must not sit on crossings of unrelated nets."""
    errors: list[str] = []
    signal = [s for s in segments if not s[4]]
    for i, a in enumerate(signal):
        nets_a = _segment_nets(a, tmap)
        for b in signal[i + 1 :]:
            cross = _segments_cross(a, b)
            if cross is None:
                continue
            nets_b = _segment_nets(b, tmap)
            if not nets_a or not nets_b or not nets_a.isdisjoint(nets_b):
                continue
            if cross in junctions:
                errors.append(
                    f"junction dot at ({cross[0]}, {cross[1]}) connects unrelated nets "
                    f"{sorted(nets_a)} vs {sorted(nets_b)}"
                )
    return errors


def verify_schematic_connectivity(
    devices: list[SpiceDevice],
    result: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    svg = render_schematic_svg(devices, result)
    layout = build_schematic_layout(devices, result)
    placed = layout.placed
    nets = _collect_net_points(placed)
    segments = parse_wire_segments(svg)
    tmap = terminal_map(placed)
    junctions = junction_points(svg)
    allowed = _allowed_dangling_points(placed, nets, layout.width, layout.height, svg)

    for pt, pins in tmap.items():
        if any(n == "0" for _, n in pins):
            if pt in allowed or any(_near(Point(*pt), Point(*a)) for a in allowed):
                continue
        if any(n.lower() in ("vdd", "vdd3") for _, n in pins):
            if _terminal_on_wire(pt, segments) or pt in allowed:
                continue
        if any(n.lower().startswith("vin") for _, n in pins):
            continue
        if not _terminal_on_wire(pt, segments):
            devs = ", ".join(f"{d}.{n}" for d, n in pins)
            errors.append(f"terminal ({pt[0]}, {pt[1]}) ({devs}) not on any wire")

    endpoint_degree: dict[tuple[int, int], int] = defaultdict(int)
    for x1, y1, x2, y2, is_io in segments:
        if is_io:
            continue
        endpoint_degree[(x1, y1)] += 1
        endpoint_degree[(x2, y2)] += 1

    signal_segments = [s for s in segments if not s[4]]
    for x1, y1, x2, y2, is_io in segments:
        if is_io:
            continue
        for x, y in ((x1, y1), (x2, y2)):
            if endpoint_degree[(x, y)] >= 2:
                continue
            # A tap can terminate on the interior of an existing segment without
            # creating a shared endpoint; treat that as connected, not dangling.
            if any(
                not (
                    (sx1 == x1 and sy1 == y1 and sx2 == x2 and sy2 == y2)
                    or (sx1 == x2 and sy1 == y2 and sx2 == x1 and sy2 == y1)
                )
                and _point_on_segment(x, y, sx1, sy1, sx2, sy2)
                for sx1, sy1, sx2, sy2, _ in signal_segments
            ):
                continue
            if (x, y) in allowed:
                continue
            if any(_near(Point(x, y), Point(*a)) for a in allowed):
                continue
            errors.append(f"dangling wire endpoint ({x}, {y})")

    placed_names = {
        f"{pd.dev.name.upper()}.{pin}"
        for pd in placed
        for _, pin, _ in terminal_refs(pd.dev, pd.origin, mirror=pd.mirror)
    }
    nl_adj = {
        net: {p for p in pins if p[0] in placed_names}
        for net, pins in netlist_adjacency(devices).items()
    }
    sch_adj = schematic_adjacency_from_wires(placed, segments)
    for net, pins in nl_adj.items():
        if net == "0" or not pins:
            continue
        missing = pins - sch_adj.get(net, set())
        if missing:
            errors.append(f"net {net}: missing pins in wire graph: {sorted(missing)}")
    for net, pins in sch_adj.items():
        if net == "0" or not pins:
            continue
        extra = pins - nl_adj.get(net, set())
        if extra:
            errors.append(f"net {net}: extra pins in wire graph: {sorted(extra)}")

    errors.extend(_false_junction_at_crossings(segments, tmap, junctions))
    errors.extend(_verify_io_stubs(placed, segments))
    errors.extend(_verify_render_geometry(placed))

    return errors


def anchor_wire_diffs(
    devices: list[SpiceDevice],
    result: dict[str, Any],
) -> list[str]:
    """Report non-rail terminals not lying on a routed wire segment."""
    svg = render_schematic_svg(devices, result)
    layout = build_schematic_layout(devices, result)
    segments = parse_wire_segments(svg)
    nets = _collect_net_points(layout.placed)
    rail_pts = _rail_endpoints(layout.placed, nets, layout.width, layout.height)
    diffs: list[str] = []
    for pd in layout.placed:
        for node, pin, pt in terminal_refs(pd.dev, pd.origin, mirror=pd.mirror):
            key = _pt_key(pt)
            if node == "0":
                if key in rail_pts or any(_near(pt, Point(*r)) for r in rail_pts):
                    continue
            if node.lower() in ("vdd", "vdd3"):
                if _terminal_on_wire(key, segments) or key in rail_pts:
                    continue
            if node.lower().startswith("vin") or node.lower() in ("inp", "inn"):
                if _terminal_on_segment(key, segments, io_only=True):
                    continue
                diffs.append(
                    f"{pd.dev.name}.{pin}:{node} anchor ({pt.x}, {pt.y}) not on wire or io-stub"
                )
                continue
            if _terminal_on_wire(key, segments):
                continue
            diffs.append(f"{pd.dev.name}.{pin}:{node} anchor ({pt.x}, {pt.y}) not on wire")
    return diffs


def verify_terminal_stubs(
    placed: list[PlacedDevice],
    svg: str,
) -> list[str]:
    """Every device terminal must have a collinear stub before the first fold."""
    errors: list[str] = []
    stub_segs = parse_terminal_stub_segments(svg)
    for pd in placed:
        for node, pin, pt in terminal_refs(pd.dev, pd.origin, mirror=pd.mirror):
            nl = node.lower()
            if node == "0" or nl in ("vdd", "vdd3") or nl.startswith("vin"):
                continue
            stub = terminal_stub(pd.dev, pd.origin, node, mirror=pd.mirror, pin=pin, terminal=pt)
            tx, ty = pt.x, pt.y
            sx, sy = stub.stub_end.x, stub.stub_end.y

            stub_seg = None
            for x1, y1, x2, y2 in stub_segs:
                ends = {(x1, y1), (x2, y2)}
                if (tx, ty) in ends and (sx, sy) in ends:
                    stub_seg = (x1, y1, x2, y2)
                    break
            if stub_seg is None:
                errors.append(
                    f"{pd.dev.name}.{pin}:{node}: missing collinear stub from ({tx},{ty}) to ({sx},{sy})"
                )
                continue

            x1, y1, x2, y2 = stub_seg
            dx, dy = sx - tx, sy - ty
            seg_dx, seg_dy = x2 - x1, y2 - y1
            length = abs(seg_dx) + abs(seg_dy)
            if abs(length - STUB_LEN) > 1:
                errors.append(
                    f"{pd.dev.name}.{pin}:{node}: stub length {length} != {STUB_LEN}px escape"
                )
            if not ((dx == 0 and seg_dx == 0) or (dy == 0 and seg_dy == 0)):
                errors.append(
                    f"{pd.dev.name}.{pin}:{node}: stub not collinear with natural direction"
                )
            if (dx != 0 and (seg_dx // abs(seg_dx)) != (dx // abs(dx))) or (
                dy != 0 and (seg_dy // abs(seg_dy)) != (dy // abs(dy))
            ):
                errors.append(
                    f"{pd.dev.name}.{pin}:{node}: stub points wrong way from terminal"
                )
    return errors
