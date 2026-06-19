"""Orthogonal connector routing with fixed ports (visibility graph + Dijkstra).

Stage 1: terminal stubs in each pin's natural direction.
Stage 2: route stub-end anchors via a rectilinear visibility graph that
         avoids device bounding boxes.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field

from openanalog.eda.netlist_graph import SpiceDevice
from openanalog.eda.symbols import Point, snap, symbol_for_device, terminal_positions

STUB_LEN = 10
_ROUTING_MARGIN = 10
_BEND_PENALTY = 5


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


def _two_term_stub_vectors(sym: object, mirror: bool) -> dict[str, tuple[int, int]]:
    p = sym.anchors["p"]  # type: ignore[attr-defined]
    n = sym.anchors["n"]  # type: ignore[attr-defined]
    if abs(p.y - n.y) > abs(p.x - n.x):
        return {"p": (0, -STUB_LEN), "n": (0, STUB_LEN)}
    px = STUB_LEN if mirror else -STUB_LEN
    nx = -STUB_LEN if mirror else STUB_LEN
    return {"p": (px, 0), "n": (nx, 0)}


def _mos_stub_vector(anchor: str, mirror: bool) -> tuple[int, int]:
    if anchor == "g":
        return (STUB_LEN, 0) if mirror else (-STUB_LEN, 0)
    if anchor == "d":
        return (0, -STUB_LEN)
    if anchor == "s":
        return (0, STUB_LEN)
    raise ValueError(f"unknown mos anchor {anchor}")


def _anchor_name_for_node(dev: SpiceDevice, node: str, *, mirror: bool) -> str:
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
) -> TerminalStub:
    sym = symbol_for_device(dev)
    terminal = terminal_positions(dev, origin, mirror=mirror)[node]
    anchor = _anchor_name_for_node(dev, node, mirror=mirror)
    if dev.kind == "M":
        dx, dy = _mos_stub_vector(anchor, mirror)
    else:
        vecs = _two_term_stub_vectors(sym, mirror)
        dx, dy = vecs[anchor]
    stub_end = Point(terminal.x + dx, terminal.y + dy)
    horizontal = dy == 0
    return TerminalStub(
        dev_name=dev.name.upper(),
        node=node.lower(),
        terminal=terminal,
        stub_end=stub_end,
        horizontal=horizontal,
        outward_dx=dx // STUB_LEN if dx else 0,
        outward_dy=dy // STUB_LEN if dy else 0,
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
            mid1 = Point(end.x, start.y)
            mid2 = Point(start.x, end.y)
            candidates: list[list[Point]] = []
            if _visible(start, mid1, obstacles) and _visible(mid1, end, obstacles):
                candidates.append([start, mid1, end])
            if _visible(start, mid2, obstacles) and _visible(mid2, end, obstacles):
                candidates.append([start, mid2, end])
            if not candidates:
                return None
            return min(candidates, key=lambda p: sum(_manhattan(p[i], p[i + 1]) for i in range(len(p) - 1)))

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
        return None

    path: list[Point] = []
    cur: tuple[int, int] | None = end_key
    while cur is not None:
        path.append(Point(cur[0], cur[1]))
        cur = prev[cur][0] if cur in prev else None
    path.reverse()
    return path


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


def _junction_points(segments: list[RoutedSegment]) -> set[Point]:
    degree: dict[tuple[int, int], int] = {}
    for s in segments:
        for x, y in ((s.x1, s.y1), (s.x2, s.y2)):
            degree[(x, y)] = degree.get((x, y), 0) + 1
    return {Point(x, y) for (x, y), d in degree.items() if d >= 3}


def route_nets(
    placed: list,
    *,
    rail_names: frozenset[str] | None = None,
) -> RouteResult:
    """Route all signal nets for placed devices."""
    rails = rail_names or frozenset({"vdd", "vdd3", "0"})
    obstacles = device_obstacles(placed)

    net_stubs: dict[str, list[TerminalStub]] = {}
    for pd in placed:
        for node in pd.dev.nodes:
            if node == "0" or node.lower() in rails:
                continue
            stub = terminal_stub(pd.dev, pd.origin, node, mirror=pd.mirror)
            net_stubs.setdefault(node.lower(), []).append(stub)

    all_segments: list[RoutedSegment] = []
    all_junctions: set[Point] = set()

    graph_nodes = _collect_graph_nodes(
        [s for stubs in net_stubs.values() for s in stubs],
        obstacles,
    )

    for net_name, stubs in net_stubs.items():
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

        ends = [s.stub_end for s in stubs]
        unique_ends: list[Point] = []
        seen: set[tuple[int, int]] = set()
        for p in ends:
            k = (p.x, p.y)
            if k not in seen:
                seen.add(k)
                unique_ends.append(p)

        if len(unique_ends) == 1:
            continue

        for i, j in _mst_edges(unique_ends):
            path = _shortest_path(unique_ends[i], unique_ends[j], graph_nodes, obstacles)
            if path is None:
                mid = Point(
                    snap((unique_ends[i].x + unique_ends[j].x) // 2),
                    snap((unique_ends[i].y + unique_ends[j].y) // 2),
                )
                path = [unique_ends[i], mid, unique_ends[j]]
            all_segments.extend(_path_to_segments(path, net_name))

        net_segs = [s for s in all_segments if s.net == net_name and s.kind == "wire"]
        if len(stubs) >= 3:
            all_junctions |= _junction_points(net_segs)

    all_segments = _merge_collinear(all_segments)
    return RouteResult(segments=all_segments, junctions=all_junctions)


def segments_to_svg_lines(segments: list[RoutedSegment], wire_class: str, rail_class: str) -> str:
    lines: list[str] = []
    for s in segments:
        if s.kind == "rail":
            cls = rail_class
        elif s.kind == "stub":
            cls = f'{wire_class} terminal-stub'
        else:
            cls = wire_class
        lines.append(f'<line x1="{s.x1}" y1="{s.y1}" x2="{s.x2}" y2="{s.y2}" {cls}/>')
    return ("\n".join(lines) + "\n") if lines else ""
