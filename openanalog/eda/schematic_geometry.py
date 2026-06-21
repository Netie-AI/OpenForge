"""Geometry scoring helpers for schematic tangling checks."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Segment:
    x1: int
    y1: int
    x2: int
    y2: int
    net: str
    kind: str = "wire"  # wire | rail | stub

    def __post_init__(self) -> None:
        if self.x1 != self.x2 and self.y1 != self.y2:
            raise ValueError(f"non-Manhattan segment: {self}")

    @property
    def is_horizontal(self) -> bool:
        return self.y1 == self.y2

    @property
    def is_vertical(self) -> bool:
        return self.x1 == self.x2

    @property
    def x_range(self) -> tuple[int, int]:
        return (self.x1, self.x2) if self.x1 <= self.x2 else (self.x2, self.x1)

    @property
    def y_range(self) -> tuple[int, int]:
        return (self.y1, self.y2) if self.y1 <= self.y2 else (self.y2, self.y1)


@dataclass(frozen=True)
class DeviceBox:
    name: str
    x: int
    y: int
    w: int
    h: int
    terminal_nets: frozenset[str]
    inset: int = 3

    @property
    def rect(self) -> tuple[int, int, int, int]:
        return (
            self.x + self.inset,
            self.y + self.inset,
            self.x + self.w - self.inset,
            self.y + self.h - self.inset,
        )


@dataclass(frozen=True)
class Crossing:
    a: Segment
    b: Segment
    point: tuple[float, float]
    reason: str  # "net-net crossing" | "wire-through-device"


def _overlap_1d(a: tuple[int, int], b: tuple[int, int]) -> tuple[float, float] | None:
    lo = max(a[0], b[0])
    hi = min(a[1], b[1])
    return (lo, hi) if lo <= hi else None


def collinear_overlap(a: Segment, b: Segment) -> tuple[int, int, int, int] | None:
    """Return (axis, coord, lo, hi) for shared-track overlap between different nets."""
    if a.net == b.net:
        return None
    if a.is_horizontal and b.is_horizontal and a.y1 == b.y1:
        ov = _overlap_1d(a.x_range, b.x_range)
        if ov is None or ov[0] >= ov[1]:
            return None
        return (0, a.y1, int(ov[0]), int(ov[1]))
    if a.is_vertical and b.is_vertical and a.x1 == b.x1:
        ov = _overlap_1d(a.y_range, b.y_range)
        if ov is None or ov[0] >= ov[1]:
            return None
        return (1, a.x1, int(ov[0]), int(ov[1]))
    return None


def find_collinear_overlaps(segments: list[Segment]) -> list[tuple[Segment, Segment, tuple[int, int, int, int]]]:
    """Pairs of unrelated-net segments sharing a collinear track span."""
    overlaps: list[tuple[Segment, Segment, tuple[int, int, int, int]]] = []
    for i, a in enumerate(segments):
        if a.kind not in ("wire", "stub"):
            continue
        for b in segments[i + 1 :]:
            if b.kind not in ("wire", "stub"):
                continue
            hit = collinear_overlap(a, b)
            if hit is not None:
                overlaps.append((a, b, hit))
    return overlaps


def segments_intersect(a: Segment, b: Segment) -> tuple[float, float] | None:
    # Collinear track sharing is a routing bug, not a perpendicular crossing.
    if (a.is_horizontal and b.is_horizontal) or (a.is_vertical and b.is_vertical):
        return None

    h, v = (a, b) if a.is_horizontal else (b, a)
    hx0, hx1 = h.x_range
    vy0, vy1 = v.y_range
    if hx0 <= v.x1 <= hx1 and vy0 <= h.y1 <= vy1:
        return (float(v.x1), float(h.y1))
    return None


def _segment_crosses_rect(seg: Segment, rect: tuple[int, int, int, int]) -> bool:
    rx0, ry0, rx1, ry1 = rect
    if seg.is_horizontal:
        return ry0 <= seg.y1 <= ry1 and _overlap_1d(seg.x_range, (rx0, rx1)) is not None
    return rx0 <= seg.x1 <= rx1 and _overlap_1d(seg.y_range, (ry0, ry1)) is not None


def find_bad_crossings(
    segments: list[Segment],
    junctions: set[tuple[int, int]],
    device_boxes: list[DeviceBox] | None = None,
) -> list[Crossing]:
    bad: list[Crossing] = []

    for i, a in enumerate(segments):
        for b in segments[i + 1 :]:
            if a.net == b.net:
                continue
            if a.kind == "rail" and b.kind == "rail":
                continue
            pt = segments_intersect(a, b)
            if pt is None:
                continue
            rounded = (round(pt[0]), round(pt[1]))
            if rounded in junctions:
                continue
            bad.append(Crossing(a, b, pt, "net-net crossing"))

    for box in device_boxes or []:
        for seg in segments:
            if seg.net in box.terminal_nets:
                continue
            if _segment_crosses_rect(seg, box.rect):
                mid = ((seg.x1 + seg.x2) / 2, (seg.y1 + seg.y2) / 2)
                bad.append(Crossing(seg, seg, mid, f"wire-through-device:{box.name}"))

    return bad


def score_layout(
    segments: list[Segment],
    junctions: set[tuple[int, int]],
    device_boxes: list[DeviceBox] | None = None,
) -> int:
    crossings = find_bad_crossings(segments, junctions, device_boxes)
    return sum(3 if c.reason.startswith("wire-through-device") else 1 for c in crossings)

