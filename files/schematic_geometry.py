"""Wire-crossing detection and layout scoring for schematic auto-routing.

This module is intentionally dependency-free (no SpiceDevice, no symbols.py)
so it can be unit-tested with synthetic fixtures and reused by any future
floorplan engine, not just the current zone-based one.

## The rule this encodes

Every wire in `schematic_layout.py` is Manhattan (horizontal or vertical
segments only — see `_manhattan()`). For axis-aligned wires, "tangled" has
a precise, checkable definition:

A crossing between segment A (net X) and segment B (net Y) is BAD unless:
  1. X == Y (two pieces of the same route touching/overlapping is normal —
     e.g. a route that doglegs through its own corner), OR
  2. the crossing point is a declared junction dot (a real 3+-way electrical
     tie — already marked as connected, not a coincidental crossing), OR
  3. both segments are rail segments (VDD/GND bus riding alongside drop
     stubs is expected and is not a readability problem).

A wire whose path cuts through the *interior* of a device symbol it isn't
electrically connected to is always BAD, regardless of net — that is a
strictly worse failure than a crossing, since it reads as "this wire touches
this transistor" to anyone looking at the schematic.

This module does not try to fix layouts. It scores them. `schematic_layout.py`
uses the score to choose between placement variants (see SKILL.md).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Segment:
    x1: int
    y1: int
    x2: int
    y2: int
    net: str
    kind: str = "wire"  # "wire" | "rail" | "stub"

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
    """Axis-aligned bounding box for a placed device symbol."""

    name: str
    x: int
    y: int
    w: int
    h: int
    terminal_nets: frozenset[str]
    # Shrink the box before testing wire intersection so terminal stubs that
    # legitimately touch the boundary (by design, every device's pins sit on
    # its own bbox edge) don't get flagged. Only flag wires that cut through
    # the body of the symbol.
    inset: int = 3

    @property
    def rect(self) -> tuple[int, int, int, int]:
        return (self.x + self.inset, self.y + self.inset,
                self.x + self.w - self.inset, self.y + self.h - self.inset)


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


def segments_intersect(a: Segment, b: Segment) -> tuple[float, float] | None:
    """Return an intersection point for two Manhattan segments, or None.

    For collinear overlaps (both horizontal at the same y, or both vertical
    at the same x, with overlapping range) this returns the midpoint of the
    overlap — good enough for junction-dot membership tests, since junction
    dots are always declared at a single point, never as a range.
    """
    if a.is_horizontal and b.is_horizontal:
        if a.y1 != b.y1:
            return None
        ov = _overlap_1d(a.x_range, b.x_range)
        return None if ov is None else ((ov[0] + ov[1]) / 2, a.y1)

    if a.is_vertical and b.is_vertical:
        if a.x1 != b.x1:
            return None
        ov = _overlap_1d(a.y_range, b.y_range)
        return None if ov is None else (a.x1, (ov[0] + ov[1]) / 2)

    # one horizontal, one vertical
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
    """The tangling check. Returns every crossing that should not exist."""
    bad: list[Crossing] = []

    for i, a in enumerate(segments):
        for b in segments[i + 1:]:
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
    """Lower is better. Used to rank placement variants against each other."""
    crossings = find_bad_crossings(segments, junctions, device_boxes)
    # wire-through-device is worse than a plain crossing — weight it harder
    # so the search never trades "fewer crossings" for "cuts through a FET".
    return sum(3 if c.reason.startswith("wire-through-device") else 1 for c in crossings)
