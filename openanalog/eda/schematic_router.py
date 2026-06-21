"""Orthogonal connector routing with fixed ports (visibility graph + Dijkstra).

Stage 1: terminal stubs in each pin's natural direction.
Stage 2: route stub-end anchors via a rectilinear visibility graph that
         avoids device bounding boxes.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field

from openanalog.eda.netlist_graph import SpiceDevice
from openanalog.eda.symbols import Point, pin_escape_profile, snap, symbol_for_device, terminal_positions, terminal_refs

STUB_LEN = 10
_ROUTING_MARGIN = 10
# A net's own pins sit on the device body edge (terminal escapes land exactly on the
# bounding box). Use a zero margin for devices this net connects to so those pins are
# reachable (pin breakout) — the bulk interior still blocks via strict-inequality
# interior tests, so a wire cannot slice through a device it connects to.
_OWN_DEVICE_MARGIN = 0
_BEND_PENALTY = 5
_TRACK_PITCH = 12


@dataclass(frozen=True)
class Rect:
    x0: int
    y0: int
    x1: int
    y1: int

    def contains_interior(self, x: int, y: int) -> bool:
        return self.x0 < x < self.x1 and self.y0 < y < self.y1


@dataclass
class TerminalStub:
    dev_name: str
    node: str
    terminal: Point
    stub_end: Point
    escape_length: int
    horizontal: bool
    outward_dx: int
    outward_dy: int


@dataclass
class RoutedSegment:
    x1: int
    y1: int
    x2: int
    y2: int
    net: str
    kind: str = "wire"  # wire | stub


@dataclass
class RouteResult:
    segments: list[RoutedSegment] = field(default_factory=list)
    junctions: set[Point] = field(default_factory=set)


def _anchor_name_for_node(dev: SpiceDevice, node: str, *, pin: str | None = None) -> str:
    if pin:
        return pin
    if dev.kind == "M":
        idx = dev.nodes.index(node)
        return ("d", "g", "s")[idx]
    idx = dev.nodes.index(node)
    return ("p", "n")[idx]


def terminal_stub(
    dev: SpiceDevice,
    origin: Point,
    node: str,
    *,
    mirror: bool = False,
    pin: str | None = None,
    terminal: Point | None = None,
) -> TerminalStub:
    term = terminal if terminal is not None else terminal_positions(dev, origin, mirror=mirror)[node]
    anchor = _anchor_name_for_node(dev, node, pin=pin)
    escape = pin_escape_profile(dev, anchor, mirror=mirror, escape_length=STUB_LEN)
    dx = escape.direction[0] * escape.escape_length
    dy = escape.direction[1] * escape.escape_length
    stub_end = Point(term.x + dx, term.y + dy)
    horizontal = dy == 0
    return TerminalStub(
        dev_name=dev.name.upper(),
        node=node.lower(),
        terminal=term,
        stub_end=stub_end,
        escape_length=escape.escape_length,
        horizontal=horizontal,
        outward_dx=escape.direction[0],
        outward_dy=escape.direction[1],
    )


def device_obstacles(
    placed: list,
    *,
    margin: int = _ROUTING_MARGIN,
) -> list[Rect]:
    rects: list[Rect] = []
    for pd in placed:
        sym = symbol_for_device(pd.dev)
        x0 = pd.origin.x - margin
        y0 = pd.origin.y - margin
        x1 = pd.origin.x + sym.width + margin
        y1 = pd.origin.y + sym.height + margin
        rects.append(Rect(x0, y0, x1, y1))
    return rects


def _device_terminal_nets(pd) -> set[str]:
    return {
        node.lower()
        for node, _, _ in terminal_refs(pd.dev, pd.origin, mirror=pd.mirror)
    }


def device_obstacles_for_net(
    placed: list,
    net_name: str,
    *,
    own_margin: int = _OWN_DEVICE_MARGIN,
    other_margin: int = _ROUTING_MARGIN,
) -> list[Rect]:
    """Obstacles tuned per net: devices this net connects to keep a small margin
    (so their pins are reachable for breakout), others keep full clearance."""
    rects: list[Rect] = []
    for pd in placed:
        sym = symbol_for_device(pd.dev)
        margin = own_margin if net_name in _device_terminal_nets(pd) else other_margin
        rects.append(
            Rect(
                pd.origin.x - margin,
                pd.origin.y - margin,
                pd.origin.x + sym.width + margin,
                pd.origin.y + sym.height + margin,
            )
        )
    return rects


def _segment_blocked(x1: int, y1: int, x2: int, y2: int, obstacles: list[Rect]) -> bool:
    if x1 == x2:
        x, y_lo, y_hi = x1, min(y1, y2), max(y1, y2)
        for obs in obstacles:
            if obs.x0 < x < obs.x1 and obs.y_range_overlaps(y_lo, y_hi):
                return True
        return False
    if y1 == y2:
        y, x_lo, x_hi = y1, min(x1, x2), max(x1, x2)
        for obs in obstacles:
            if obs.y0 < y < obs.y1 and obs.x_range_overlaps(x_lo, x_hi):
                return True
        return False
    return True


def _attach_rect_methods() -> None:
    def x_range_overlaps(self: Rect, lo: int, hi: int) -> bool:
        return max(self.x0, lo) < min(self.x1, hi)

    def y_range_overlaps(self: Rect, lo: int, hi: int) -> bool:
        return max(self.y0, lo) < min(self.y1, hi)

    Rect.x_range_overlaps = x_range_overlaps  # type: ignore[attr-defined]
    Rect.y_range_overlaps = y_range_overlaps  # type: ignore[attr-defined]


_attach_rect_methods()


def _collect_graph_nodes(stubs: list[TerminalStub], obstacles: list[Rect]) -> list[Point]:
    nodes: set[tuple[int, int]] = set()
    for stub in stubs:
        nodes.add((stub.stub_end.x, stub.stub_end.y))
    for obs in obstacles:
        for x in (obs.x0, obs.x1):
            for y in (obs.y0, obs.y1):
                nodes.add((snap(x), snap(y)))
    return [Point(x, y) for x, y in nodes]


def _visible(a: Point, b: Point, obstacles: list[Rect]) -> bool:
    if a.x != b.x and a.y != b.y:
        return False
    return not _segment_blocked(a.x, a.y, b.x, b.y, obstacles)


def _manhattan(a: Point, b: Point) -> int:
    return abs(a.x - b.x) + abs(a.y - b.y)


def _path_to_segments(path: list[Point], net: str) -> list[RoutedSegment]:
    segs: list[RoutedSegment] = []
    for i in range(len(path) - 1):
        a, b = path[i], path[i + 1]
        segs.append(RoutedSegment(a.x, a.y, b.x, b.y, net))
    return segs


def _path_len(path: list[Point]) -> int:
    return sum(_manhattan(path[i], path[i + 1]) for i in range(len(path) - 1))


def _path_bends(path: list[Point]) -> int:
    bends = 0
    prev_dir: str | None = None
    for i in range(len(path) - 1):
        a, b = path[i], path[i + 1]
        cur_dir = "v" if a.x == b.x else "h"
        if prev_dir and cur_dir != prev_dir:
            bends += 1
        prev_dir = cur_dir
    return bends


def _compress_path(path: list[Point]) -> list[Point]:
    if not path:
        return []
    out: list[Point] = [path[0]]
    for pt in path[1:]:
        if pt.x == out[-1].x and pt.y == out[-1].y:
            continue
        out.append(pt)
    if len(out) <= 2:
        return out
    compressed: list[Point] = [out[0]]
    for i in range(1, len(out) - 1):
        a = compressed[-1]
        b = out[i]
        c = out[i + 1]
        if (a.x == b.x == c.x) or (a.y == b.y == c.y):
            continue
        compressed.append(b)
    compressed.append(out[-1])
    return compressed


def _path_visible(path: list[Point], obstacles: list[Rect]) -> bool:
    return all(_visible(path[i], path[i + 1], obstacles) for i in range(len(path) - 1))


def _fallback_manhattan_path(
    start: Point,
    end: Point,
    nodes: list[Point],
    obstacles: list[Rect],
) -> list[Point] | None:
    """Axis-aligned fallback when visibility-graph routing cannot close a net."""
    candidates: list[list[Point]] = []

    def add_candidate(path: list[Point]) -> None:
        path = _compress_path(path)
        if len(path) >= 2 and _path_visible(path, obstacles):
            candidates.append(path)

    add_candidate([start, Point(end.x, start.y), end])
    add_candidate([start, Point(start.x, end.y), end])

    xs = {start.x, end.x, snap((start.x + end.x) // 2)}
    ys = {start.y, end.y, snap((start.y + end.y) // 2)}
    for pt in nodes:
        xs.add(pt.x)
        ys.add(pt.y)
    for delta in (10, 20, 30, 40):
        xs.add(snap(start.x - delta))
        xs.add(snap(start.x + delta))
        xs.add(snap(end.x - delta))
        xs.add(snap(end.x + delta))
        ys.add(snap(start.y - delta))
        ys.add(snap(start.y + delta))
        ys.add(snap(end.y - delta))
        ys.add(snap(end.y + delta))

    for x in xs:
        add_candidate([start, Point(x, start.y), Point(x, end.y), end])
    for y in ys:
        add_candidate([start, Point(start.x, y), Point(end.x, y), end])

    if candidates:
        return min(candidates, key=lambda p: (_path_len(p), _path_bends(p)))
    return None


def _shortest_path(
    start: Point,
    end: Point,
    nodes: list[Point],
    obstacles: list[Rect],
) -> list[Point] | None:
    if start.x == end.x and start.y == end.y:
        return [start]

    visible_from: dict[tuple[int, int], list[Point]] = {}
    all_pts = nodes
    if not any(p.x == start.x and p.y == start.y for p in all_pts):
        all_pts = [start] + all_pts
    if not any(p.x == end.x and p.y == end.y for p in all_pts):
        all_pts = all_pts + [end]

    for p in all_pts:
        key = (p.x, p.y)
        visible_from[key] = [q for q in all_pts if (q.x, q.y) != key and _visible(p, q, obstacles)]

    start_key = (start.x, start.y)
    end_key = (end.x, end.y)
    if end_key not in visible_from.get(start_key, []) and start_key != end_key:
        if not _visible(start, end, obstacles):
            return _fallback_manhattan_path(start, end, all_pts, obstacles)

    # Dijkstra with bend penalty
    dist: dict[tuple[int, int], int] = {start_key: 0}
    prev: dict[tuple[int, int], tuple[tuple[int, int], str | None]] = {}
    heap: list[tuple[int, int, int, str | None]] = [(0, start.x, start.y, None)]

    while heap:
        cost, x, y, in_dir = heapq.heappop(heap)
        key = (x, y)
        if cost > dist.get(key, 10**9):
            continue
        if key == end_key:
            break
        cur = Point(x, y)
        for nxt in visible_from.get(key, ()):
            nkey = (nxt.x, nxt.y)
            out_dir: str | None
            if nxt.x == cur.x:
                out_dir = "v"
            elif nxt.y == cur.y:
                out_dir = "h"
            else:
                continue
            bend = _BEND_PENALTY if in_dir and in_dir != out_dir else 0
            ncost = cost + _manhattan(cur, nxt) + bend
            if ncost < dist.get(nkey, 10**9):
                dist[nkey] = ncost
                prev[nkey] = (key, out_dir)
                heapq.heappush(heap, (ncost, nxt.x, nxt.y, out_dir))

    if end_key not in dist:
        return _fallback_manhattan_path(start, end, all_pts, obstacles)

    path: list[Point] = []
    cur: tuple[int, int] | None = end_key
    while cur is not None:
        path.append(Point(cur[0], cur[1]))
        cur = prev[cur][0] if cur in prev else None
    path.reverse()
    return _compress_path(path)


def _mst_edges(points: list[Point]) -> list[tuple[int, int]]:
    """Prim's MST on Manhattan distance."""
    if len(points) <= 1:
        return []
    in_tree = {0}
    edges: list[tuple[int, int]] = []
    while len(in_tree) < len(points):
        best: tuple[int, int, int] | None = None
        for i in in_tree:
            for j in range(len(points)):
                if j in in_tree:
                    continue
                d = _manhattan(points[i], points[j])
                if best is None or d < best[0]:
                    best = (d, i, j)
        assert best is not None
        _, i, j = best
        in_tree.add(j)
        edges.append((i, j))
    return edges


def _merge_collinear(segments: list[RoutedSegment]) -> list[RoutedSegment]:
    if not segments:
        return []
    merged: list[RoutedSegment] = []
    for seg in segments:
        if not merged:
            merged.append(seg)
            continue
        last = merged[-1]
        if (
            last.net == seg.net
            and last.kind == seg.kind
            and last.kind != "stub"
            and last.x2 == seg.x1
            and last.y2 == seg.y1
            and ((last.x1 == last.x2 == seg.x1 == seg.x2) or (last.y1 == last.y2 == seg.y1 == seg.y2))
        ):
            merged[-1] = RoutedSegment(last.x1, last.y1, seg.x2, seg.y2, last.net, last.kind)
        else:
            merged.append(seg)
    return merged


def _is_segment_endpoint(x: int, y: int, seg: RoutedSegment) -> bool:
    return (x, y) == (seg.x1, seg.y1) or (x, y) == (seg.x2, seg.y2)


def _is_segment_interior(x: int, y: int, seg: RoutedSegment) -> bool:
    if _is_segment_endpoint(x, y, seg):
        return False
    if seg.x1 == seg.x2 == x:
        return min(seg.y1, seg.y2) < y < max(seg.y1, seg.y2)
    if seg.y1 == seg.y2 == y:
        return min(seg.x1, seg.x2) < x < max(seg.x1, seg.x2)
    return False


def _routed_collinear_overlap(a: RoutedSegment, b: RoutedSegment) -> bool:
    if a.net == b.net or a.kind != "wire" or b.kind != "wire":
        return False
    if a.y1 == a.y2 == b.y1 == b.y2:
        lo = max(min(a.x1, a.x2), min(b.x1, b.x2))
        hi = min(max(a.x1, a.x2), max(b.x1, b.x2))
        return lo < hi
    if a.x1 == a.x2 == b.x1 == b.x2:
        lo = max(min(a.y1, a.y2), min(b.y1, b.y2))
        hi = min(max(a.y1, a.y2), max(b.y1, b.y2))
        return lo < hi
    return False


def _path_collinear_conflicts(
    path: list[Point],
    net: str,
    foreign_wires: list[RoutedSegment],
) -> bool:
    for seg in _path_to_segments(path, net):
        for foreign in foreign_wires:
            if _routed_collinear_overlap(seg, foreign):
                return True
    return False


def _route_avoid_collinear_foreign(
    start: Point,
    end: Point,
    nodes: list[Point],
    obstacles: list[Rect],
    foreign_wires: list[RoutedSegment],
    net: str,
) -> list[Point] | None:
    """Route between stub ends without sharing a track with foreign nets."""
    candidates: list[list[Point]] = []

    def consider(path: list[Point] | None) -> None:
        if not path or len(path) < 2:
            return
        path = _compress_path(path)
        if len(path) < 2 or not _path_visible(path, obstacles):
            return
        if not _path_collinear_conflicts(path, net, foreign_wires):
            candidates.append(path)

    consider(_shortest_path(start, end, nodes, obstacles))
    consider(_fallback_manhattan_path(start, end, nodes, obstacles))

    corner_paths = [
        [start, Point(end.x, start.y), end],
        [start, Point(start.x, end.y), end],
    ]
    for raw in corner_paths:
        consider(_compress_path(raw))

    y_refs = {start.y, end.y, snap((start.y + end.y) // 2)}
    x_refs = {start.x, end.x, snap((start.x + end.x) // 2)}
    for pt in nodes:
        y_refs.add(pt.y)
        x_refs.add(pt.x)
    for pitch in (_TRACK_PITCH, _TRACK_PITCH * 2, -_TRACK_PITCH, -_TRACK_PITCH * 2, _TRACK_PITCH * 3):
        y_refs.add(snap(start.y + pitch))
        y_refs.add(snap(end.y + pitch))
        x_refs.add(snap(start.x + pitch))
        x_refs.add(snap(end.x + pitch))

    for y in y_refs:
        consider(_compress_path([start, Point(start.x, y), Point(end.x, y), end]))
    for x in x_refs:
        consider(_compress_path([start, Point(x, start.y), Point(x, end.y), end]))

    if not candidates:
        return _shortest_path(start, end, nodes, obstacles)
    return min(candidates, key=lambda p: (_path_len(p), _path_bends(p)))


def electrical_junction_points(segments: list[RoutedSegment]) -> set[Point]:
    """Junction dots: 3+ arms on one net only — never where a foreign net shares the point."""
    sig = [s for s in segments if s.kind in ("wire", "stub")]
    if not sig:
        return set()
    candidates: set[tuple[int, int]] = set()
    for seg in sig:
        candidates.add((seg.x1, seg.y1))
        candidates.add((seg.x2, seg.y2))
    junctions: set[Point] = set()
    for x, y in candidates:
        nets_at: set[str] = set()
        degree_by_net: dict[str, int] = {}
        for seg in sig:
            if _is_segment_endpoint(x, y, seg):
                nets_at.add(seg.net)
                degree_by_net[seg.net] = degree_by_net.get(seg.net, 0) + 1
            elif _is_segment_interior(x, y, seg):
                nets_at.add(seg.net)
                degree_by_net[seg.net] = degree_by_net.get(seg.net, 0) + 2
        if len(nets_at) != 1:
            continue
        sole_net = next(iter(nets_at))
        if degree_by_net.get(sole_net, 0) >= 3:
            junctions.add(Point(x, y))
    return junctions


def _repair_collinear_overlaps(segments: list[RoutedSegment]) -> list[RoutedSegment]:
    """Jog one net off a shared track when two nets collinearly overlap."""
    out = list(segments)
    for _ in range(32):
        repair: tuple[int, list[RoutedSegment]] | None = None
        for i, a in enumerate(out):
            if a.kind != "wire":
                continue
            for j, b in enumerate(out):
                if j <= i or b.kind != "wire" or a.net == b.net:
                    continue
                if a.y1 == a.y2 == b.y1 == b.y2:
                    x_lo = max(min(a.x1, a.x2), min(b.x1, b.x2))
                    x_hi = min(max(a.x1, a.x2), max(b.x1, b.x2))
                    if x_lo >= x_hi:
                        continue
                    victim = a if a.net < b.net else b
                    vi = i if victim is a else j
                    y = victim.y1
                    alt_y = y - _TRACK_PITCH if y - _TRACK_PITCH >= 40 else y + _TRACK_PITCH
                    jog_x = x_lo - _TRACK_PITCH
                    if jog_x < 40:
                        jog_x = x_hi + _TRACK_PITCH
                    vx_lo, vx_hi = sorted((victim.x1, victim.x2))
                    pieces: list[RoutedSegment] = []
                    if vx_lo < jog_x:
                        pieces.append(RoutedSegment(vx_lo, y, jog_x, y, victim.net))
                    pieces.append(RoutedSegment(jog_x, y, jog_x, alt_y, victim.net))
                    pieces.append(RoutedSegment(jog_x, alt_y, x_hi, alt_y, victim.net))
                    if x_hi < vx_hi:
                        pieces.append(RoutedSegment(x_hi, alt_y, x_hi, y, victim.net))
                        pieces.append(RoutedSegment(x_hi, y, vx_hi, y, victim.net))
                    repair = (vi, pieces)
                    break
                if a.x1 == a.x2 == b.x1 == b.x2:
                    y_lo = max(min(a.y1, a.y2), min(b.y1, b.y2))
                    y_hi = min(max(a.y1, a.y2), max(b.y1, b.y2))
                    if y_lo >= y_hi:
                        continue
                    victim = a if a.net < b.net else b
                    vi = i if victim is a else j
                    x = victim.x1
                    alt_x = x - _TRACK_PITCH if x - _TRACK_PITCH >= 40 else x + _TRACK_PITCH
                    vy_lo, vy_hi = sorted((victim.y1, victim.y2))
                    pieces = []
                    if vy_lo < y_lo:
                        pieces.append(RoutedSegment(x, vy_lo, x, y_lo, victim.net))
                    pieces.append(RoutedSegment(x, y_lo, alt_x, y_lo, victim.net))
                    pieces.append(RoutedSegment(alt_x, y_lo, alt_x, y_hi, victim.net))
                    if y_hi < vy_hi:
                        pieces.append(RoutedSegment(alt_x, y_hi, x, y_hi, victim.net))
                        pieces.append(RoutedSegment(x, y_hi, x, vy_hi, victim.net))
                    repair = (vi, pieces)
                    break
            if repair:
                break
        if repair is None:
            break
        vi, pieces = repair
        out.pop(vi)
        out[vi:vi] = pieces
    return out


def _trim_redundant_vertical_spurs(segments: list[RoutedSegment]) -> list[RoutedSegment]:
    """Drop vertical legs past a same-net horizontal jog when the far end is a degree-1 spur."""
    from collections import defaultdict

    by_net: dict[str, list[RoutedSegment]] = defaultdict(list)
    for seg in segments:
        by_net[seg.net].append(seg)

    def endpoint_degree(net_segs: list[RoutedSegment], px: int, py: int) -> int:
        degree = 0
        for s in net_segs:
            if (s.x1, s.y1) == (px, py):
                degree += 1
            if (s.x2, s.y2) == (px, py):
                degree += 1
        return degree

    trimmed: list[RoutedSegment] = []
    for seg in segments:
        if seg.kind != "wire" or seg.x1 != seg.x2:
            trimmed.append(seg)
            continue
        x = seg.x1
        net_segs = by_net[seg.net]
        horiz_y_at_x = set()
        for other in net_segs:
            if other.y1 != other.y2:
                continue
            if other.x1 == x:
                horiz_y_at_x.add(other.y1)
            if other.x2 == x:
                horiz_y_at_x.add(other.y2)
        end_a = (x, seg.y1)
        end_b = (x, seg.y2)
        deg_a = endpoint_degree(net_segs, *end_a)
        deg_b = endpoint_degree(net_segs, *end_b)
        if (deg_a, deg_b) != (1, 2) and (deg_a, deg_b) != (2, 1):
            trimmed.append(seg)
            continue
        spur = end_a if deg_a == 1 else end_b
        anchor = end_b if deg_a == 1 else end_a
        y_lo, y_hi = sorted((seg.y1, seg.y2))
        trim_candidates = [y for y in horiz_y_at_x if y_lo < y < y_hi]
        if not trim_candidates:
            trimmed.append(seg)
            continue
        ty = min(trim_candidates, key=lambda y: abs(y - spur[1]))
        if spur[1] > anchor[1]:
            trimmed.append(RoutedSegment(x, ty, x, anchor[1], seg.net))
        else:
            trimmed.append(RoutedSegment(x, anchor[1], x, ty, seg.net))
    return trimmed


def _is_passive_bridge(dev: SpiceDevice) -> bool:
    return dev.kind in ("C", "R") and len(dev.nodes) == 2


def _passive_dev_names(placed: list) -> frozenset[str]:
    return frozenset(
        pd.dev.name.upper() for pd in placed if _is_passive_bridge(pd.dev)
    )


def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def _nearest_tap_on_segment(pt: Point, seg: RoutedSegment) -> tuple[Point, int]:
    """Closest Manhattan tap point on an axis-aligned wire segment."""
    if seg.x1 == seg.x2:
        x = seg.x1
        y = _clamp(pt.y, min(seg.y1, seg.y2), max(seg.y1, seg.y2))
        tap = Point(x, y)
        return tap, abs(pt.x - x) + abs(pt.y - y)
    if seg.y1 == seg.y2:
        y = seg.y1
        x = _clamp(pt.x, min(seg.x1, seg.x2), max(seg.x1, seg.x2))
        tap = Point(x, y)
        return tap, abs(pt.x - x) + abs(pt.y - y)
    return pt, 10**9


def _orthogonal_tap_segments(from_pt: Point, tap: Point, net: str) -> list[RoutedSegment]:
    """Connect stub end to backbone with one or two orthogonal legs."""
    if from_pt.x == tap.x and from_pt.y == tap.y:
        return []
    if from_pt.x == tap.x or from_pt.y == tap.y:
        return [RoutedSegment(from_pt.x, from_pt.y, tap.x, tap.y, net)]
    via_h = Point(tap.x, from_pt.y)
    via_v = Point(from_pt.x, tap.y)
    if _manhattan(from_pt, via_h) + _manhattan(via_h, tap) <= _manhattan(from_pt, via_v) + _manhattan(via_v, tap):
        path = [from_pt, via_h, tap]
    else:
        path = [from_pt, via_v, tap]
    return _path_to_segments(path, net)


def _tap_passive_stubs(
    passive_stubs: list[TerminalStub],
    net_name: str,
    wire_segs: list[RoutedSegment],
    segments_out: list[RoutedSegment],
) -> None:
    """Second pass: connect passive stub ends onto existing net wires (Miller cap taps)."""
    if not wire_segs or not passive_stubs:
        return
    for stub in passive_stubs:
        best_tap: Point | None = None
        best_dist = 10**9
        for seg in wire_segs:
            tap, dist = _nearest_tap_on_segment(stub.stub_end, seg)
            if dist < best_dist:
                best_dist = dist
                best_tap = tap
        if best_tap is None:
            continue
        segments_out.extend(_orthogonal_tap_segments(stub.stub_end, best_tap, net_name))


def _wire_obstacles(
    segments: list[RoutedSegment],
    *,
    margin: int = 4,
) -> list[Rect]:
    """Reserve existing routed tracks so later nets avoid overlapping them."""
    def segment_rect(x1: int, y1: int, x2: int, y2: int, pad: int) -> Rect | None:
        if x1 == x2:
            x = x1
            y0, y1s = sorted((y1, y2))
            return Rect(x - pad, y0 - 1, x + pad, y1s + 1)
        if y1 == y2:
            y = y1
            x0, x1s = sorted((x1, x2))
            return Rect(x0 - 1, y - pad, x1s + 1, y + pad)
        return None

    rects: list[Rect] = []
    for seg in segments:
        if seg.kind != "wire":
            continue
        rect = segment_rect(seg.x1, seg.y1, seg.x2, seg.y2, margin)
        if rect:
            rects.append(rect)
    return rects


def _foreign_escape_obstacles(
    net_stubs: dict[str, list[TerminalStub]],
    net_name: str,
    exempt_points: set[tuple[int, int]],
    *,
    margin: int = 3,
) -> list[Rect]:
    """Protect other nets' terminal escape corridors and endpoints."""
    def segment_rect(x1: int, y1: int, x2: int, y2: int, pad: int) -> Rect | None:
        if x1 == x2:
            x = x1
            y0, y1s = sorted((y1, y2))
            return Rect(x - pad, y0 - 1, x + pad, y1s + 1)
        if y1 == y2:
            y = y1
            x0, x1s = sorted((x1, x2))
            return Rect(x0 - 1, y - pad, x1s + 1, y + pad)
        return None

    rects: list[Rect] = []
    seen_rects: set[tuple[int, int, int, int]] = set()
    for other_net, stubs in net_stubs.items():
        if other_net == net_name:
            continue
        for stub in stubs:
            corridor = segment_rect(
                stub.terminal.x,
                stub.terminal.y,
                stub.stub_end.x,
                stub.stub_end.y,
                margin,
            )
            if corridor:
                if any(corridor.contains_interior(x, y) for x, y in exempt_points):
                    corridor = None
            if corridor:
                key = (corridor.x0, corridor.y0, corridor.x1, corridor.y1)
                if key not in seen_rects:
                    seen_rects.add(key)
                    rects.append(corridor)
            endpoint = Rect(
                stub.stub_end.x - margin,
                stub.stub_end.y - margin,
                stub.stub_end.x + margin,
                stub.stub_end.y + margin,
            )
            if any(endpoint.contains_interior(x, y) for x, y in exempt_points):
                continue
            ekey = (endpoint.x0, endpoint.y0, endpoint.x1, endpoint.y1)
            if ekey in seen_rects:
                continue
            seen_rects.add(ekey)
            rects.append(endpoint)
    return rects


def route_nets(
    placed: list,
    *,
    rail_names: frozenset[str] | None = None,
) -> RouteResult:
    """Route all signal nets for placed devices."""
    rails = rail_names or frozenset({"vdd", "vdd3", "0"})
    passive_names = _passive_dev_names(placed)

    net_stubs: dict[str, list[TerminalStub]] = {}
    for pd in placed:
        for node, pin, terminal in terminal_refs(pd.dev, pd.origin, mirror=pd.mirror):
            if node == "0" or node.lower() in rails:
                continue
            stub = terminal_stub(pd.dev, pd.origin, node, mirror=pd.mirror, pin=pin, terminal=terminal)
            net_stubs.setdefault(node.lower(), []).append(stub)

    all_segments: list[RoutedSegment] = []

    all_stub_points = [s for stubs in net_stubs.values() for s in stubs]

    for net_name, stubs in net_stubs.items():
        obstacles = device_obstacles_for_net(placed, net_name)
        reserved = _wire_obstacles([s for s in all_segments if s.net != net_name])
        exempt_points = {
            (stub.terminal.x, stub.terminal.y) for stub in stubs
        } | {
            (stub.stub_end.x, stub.stub_end.y) for stub in stubs
        }
        foreign_stub_guards = _foreign_escape_obstacles(net_stubs, net_name, exempt_points)
        active_obstacles = obstacles + reserved + foreign_stub_guards
        graph_nodes = _collect_graph_nodes(all_stub_points, active_obstacles)
        active_stubs = [s for s in stubs if s.dev_name not in passive_names]
        passive_stubs = [s for s in stubs if s.dev_name in passive_names]
        route_stubs = active_stubs if active_stubs else stubs

        if len(stubs) < 2:
            for stub in stubs:
                all_segments.append(
                    RoutedSegment(
                        stub.terminal.x,
                        stub.terminal.y,
                        stub.stub_end.x,
                        stub.stub_end.y,
                        net_name,
                        kind="stub",
                    )
                )
            continue

        for stub in stubs:
            all_segments.append(
                RoutedSegment(
                    stub.terminal.x,
                    stub.terminal.y,
                    stub.stub_end.x,
                    stub.stub_end.y,
                    net_name,
                    kind="stub",
                )
            )

        ends = [s.stub_end for s in route_stubs]
        unique_ends: list[Point] = []
        seen: set[tuple[int, int]] = set()
        for p in ends:
            k = (p.x, p.y)
            if k not in seen:
                seen.add(k)
                unique_ends.append(p)

        foreign_wires = [s for s in all_segments if s.net != net_name and s.kind == "wire"]

        if len(unique_ends) >= 2:
            for i, j in _mst_edges(unique_ends):
                path = _route_avoid_collinear_foreign(
                    unique_ends[i],
                    unique_ends[j],
                    graph_nodes,
                    active_obstacles,
                    foreign_wires,
                    net_name,
                )
                if path is None:
                    path = _fallback_manhattan_path(unique_ends[i], unique_ends[j], graph_nodes, active_obstacles) or [
                        unique_ends[i],
                        Point(unique_ends[j].x, unique_ends[i].y),
                        unique_ends[j],
                    ]
                all_segments.extend(_path_to_segments(path, net_name))
                foreign_wires = [s for s in all_segments if s.net != net_name and s.kind == "wire"]

        net_segs = [s for s in all_segments if s.net == net_name and s.kind == "wire"]
        _tap_passive_stubs(passive_stubs, net_name, net_segs, all_segments)

    all_segments = _merge_collinear(all_segments)
    all_segments = _repair_collinear_overlaps(all_segments)
    all_segments = _merge_collinear(all_segments)
    all_segments = _trim_redundant_vertical_spurs(all_segments)
    all_segments = _merge_collinear(all_segments)
    all_junctions = electrical_junction_points(all_segments)
    return RouteResult(segments=all_segments, junctions=all_junctions)


_HOP_RADIUS = 4


def _segment_svg_class(seg: RoutedSegment, wire_class: str, rail_class: str) -> str:
    if seg.kind == "rail":
        return rail_class
    if seg.kind == "stub":
        return wire_class.replace('signal-wire"', 'signal-wire terminal-stub"')
    return wire_class


def _append_svg_class(cls: str, extra: str) -> str:
    marker = 'class="'
    start = cls.index(marker) + len(marker)
    end = cls.index('"', start)
    return cls[:start] + cls[start:end] + f" {extra}" + cls[end:]


def _hop_points_by_segment(
    segments: list[RoutedSegment],
    junctions: set[Point],
) -> dict[int, list[tuple[int, int]]]:
    """Map segment index -> crossing centers where that segment should draw a hop."""
    from openanalog.eda.schematic_geometry import Segment, segments_intersect

    junction_set = {(j.x, j.y) for j in junctions}
    hops: dict[int, list[tuple[int, int]]] = {}
    geom = [Segment(s.x1, s.y1, s.x2, s.y2, s.net, s.kind) for s in segments]

    for i, seg_a in enumerate(segments):
        for j in range(i + 1, len(segments)):
            seg_b = segments[j]
            if seg_a.net == seg_b.net:
                continue
            if seg_a.kind == "rail" and seg_b.kind == "rail":
                continue
            pt = segments_intersect(geom[i], geom[j])
            if pt is None:
                continue
            cross = (round(pt[0]), round(pt[1]))
            if cross in junction_set:
                continue
            hop_idx = i if seg_a.net > seg_b.net else j
            hops.setdefault(hop_idx, []).append(cross)
    return hops


def _render_segment_with_hops(
    seg: RoutedSegment,
    crossings: list[tuple[int, int]],
    wire_class: str,
    rail_class: str,
) -> list[str]:
    cls = _segment_svg_class(seg, wire_class, rail_class)
    hop_cls = _append_svg_class(cls, "wire-hop")
    if not crossings:
        return [f'<line x1="{seg.x1}" y1="{seg.y1}" x2="{seg.x2}" y2="{seg.y2}" {cls}/>']

    r = _HOP_RADIUS
    parts: list[str] = []
    if seg.y1 == seg.y2:
        y = seg.y1
        x_lo, x_hi = sorted((seg.x1, seg.x2))
        xs = sorted({cx for cx, cy in crossings if x_lo < cx < x_hi and cy == y})
        cursor = x_lo
        for cx in xs:
            if cx - r > cursor:
                parts.append(f'<line x1="{cursor}" y1="{y}" x2="{cx - r}" y2="{y}" {cls}/>')
            parts.append(f'<path d="M {cx - r} {y} A {r} {r} 0 0 1 {cx + r} {y}" {hop_cls}/>')
            cursor = cx + r
        if cursor < x_hi:
            parts.append(f'<line x1="{cursor}" y1="{y}" x2="{x_hi}" y2="{y}" {cls}/>')
        return parts

    if seg.x1 == seg.x2:
        x = seg.x1
        y_lo, y_hi = sorted((seg.y1, seg.y2))
        ys = sorted({cy for cx, cy in crossings if y_lo < cy < y_hi and cx == x})
        cursor = y_lo
        for cy in ys:
            if cy - r > cursor:
                parts.append(f'<line x1="{x}" y1="{cursor}" x2="{x}" y2="{cy - r}" {cls}/>')
            parts.append(f'<path d="M {x} {cy - r} A {r} {r} 0 0 1 {x} {cy + r}" {hop_cls}/>')
            cursor = cy + r
        if cursor < y_hi:
            parts.append(f'<line x1="{x}" y1="{cursor}" x2="{x}" y2="{y_hi}" {cls}/>')
        return parts

    return [f'<line x1="{seg.x1}" y1="{seg.y1}" x2="{seg.x2}" y2="{seg.y2}" {cls}/>']


def segments_to_svg_lines(
    segments: list[RoutedSegment],
    wire_class: str,
    rail_class: str,
    *,
    junctions: set[Point] | None = None,
) -> str:
    """Emit SVG line/path elements; unrelated-net crossings get wire-hop arcs."""
    hop_map = _hop_points_by_segment(segments, junctions or set())
    lines: list[str] = []
    for idx, seg in enumerate(segments):
        lines.extend(_render_segment_with_hops(seg, hop_map.get(idx, []), wire_class, rail_class))
    return ("\n".join(lines) + "\n") if lines else ""
