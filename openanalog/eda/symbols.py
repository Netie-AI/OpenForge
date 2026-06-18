"""Fixed-geometry schematic symbols with named terminal anchors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Point:
    x: int
    y: int

    def offset(self, dx: int, dy: int) -> Point:
        return Point(self.x + dx, self.y + dy)


# Grid snap unit (pixels).
GRID = 10


def snap(v: int) -> int:
    return round(v / GRID) * GRID


@dataclass
class SymbolDef:
    """Symbol geometry relative to origin (top-left of bounding box)."""

    width: int
    height: int
    anchors: dict[str, Point]
    svg_body: str

    def anchor(self, name: str, origin: Point, *, mirror: bool = False) -> Point:
        """Return global terminal coords matching render_symbol's SVG transform."""
        pt = self.anchors[name]
        if mirror:
            # translate(origin.x + width, origin.y) scale(-1, 1)
            return Point(origin.x + self.width - pt.x, origin.y + pt.y)
        return Point(origin.x + pt.x, origin.y + pt.y)


# NMOS: gate left, drain top-right, source bottom-right; bulk arrow into channel.
_NMOS_BODY = """
<line x1="6" y1="10" x2="6" y2="38" stroke="#7aa2ff" stroke-width="1.5"/>
<line x1="16" y1="10" x2="16" y2="38" stroke="#7aa2ff" stroke-width="1.5"/>
<line x1="16" y1="10" x2="32" y2="10" stroke="#7aa2ff" stroke-width="1.5"/>
<line x1="16" y1="38" x2="32" y2="38" stroke="#7aa2ff" stroke-width="1.5"/>
<polygon points="22,38 28,35 28,41" fill="#7aa2ff"/>
"""

_NMOS = SymbolDef(
    width=36,
    height=48,
    anchors={"d": Point(32, 10), "g": Point(6, 24), "s": Point(32, 38)},
    svg_body=_NMOS_BODY,
)

# PMOS: same geometry; bulk arrow points out of channel.
_PMOS_BODY = """
<line x1="6" y1="10" x2="6" y2="38" stroke="#7aa2ff" stroke-width="1.5"/>
<line x1="16" y1="10" x2="16" y2="38" stroke="#7aa2ff" stroke-width="1.5"/>
<line x1="16" y1="10" x2="32" y2="10" stroke="#7aa2ff" stroke-width="1.5"/>
<line x1="16" y1="38" x2="32" y2="38" stroke="#7aa2ff" stroke-width="1.5"/>
<polygon points="22,10 28,7 28,13" fill="#7aa2ff"/>
"""

_PMOS = SymbolDef(
    width=36,
    height=48,
    anchors={"d": Point(32, 10), "g": Point(6, 24), "s": Point(32, 38)},
    svg_body=_PMOS_BODY,
)

_CAP_BODY = """
<line x1="4" y1="20" x2="14" y2="20" stroke="#5ad1c9" stroke-width="1.5"/>
<line x1="18" y1="14" x2="18" y2="26" stroke="#5ad1c9" stroke-width="1.5"/>
<line x1="22" y1="14" x2="22" y2="26" stroke="#5ad1c9" stroke-width="1.5"/>
<line x1="26" y1="20" x2="36" y2="20" stroke="#5ad1c9" stroke-width="1.5"/>
"""

_CAP = SymbolDef(
    width=40,
    height=40,
    anchors={"p": Point(4, 20), "n": Point(36, 20)},
    svg_body=_CAP_BODY,
)

_RES_BODY = """
<line x1="4" y1="20" x2="10" y2="20" stroke="#5ad1c9" stroke-width="1.5"/>
<polyline points="10,20 14,12 18,28 22,12 26,28 30,20" fill="none" stroke="#5ad1c9" stroke-width="1.5"/>
<line x1="30" y1="20" x2="36" y2="20" stroke="#5ad1c9" stroke-width="1.5"/>
"""

_RES = SymbolDef(
    width=40,
    height=40,
    anchors={"p": Point(4, 20), "n": Point(36, 20)},
    svg_body=_RES_BODY,
)

_ISRC_BODY = """
<circle cx="20" cy="20" r="14" fill="none" stroke="#5ad1c9" stroke-width="1.5"/>
<line x1="20" y1="10" x2="20" y2="30" stroke="#5ad1c9" stroke-width="1.5"/>
<polygon points="20,10 16,18 24,18" fill="#5ad1c9"/>
"""

_ISRC = SymbolDef(
    width=40,
    height=40,
    anchors={"p": Point(20, 6), "n": Point(20, 34)},
    svg_body=_ISRC_BODY,
)


def is_pmos(dev: Any) -> bool:
    if dev.kind != "M":
        return False
    bulk = dev.nodes[3].lower() if len(dev.nodes) > 3 else ""
    model = dev.model.lower()
    if bulk in ("vdd", "vdd3"):
        return True
    return "pmos" in model or model.startswith("p")


def mos_anchor_names(dev: Any) -> tuple[str, str, str]:
    return "d", "g", "s"


def two_term_anchors() -> tuple[str, str]:
    return "p", "n"


def symbol_for_device(dev: Any) -> SymbolDef:
    if dev.kind == "M":
        return _PMOS if is_pmos(dev) else _NMOS
    if dev.kind == "C":
        return _CAP
    if dev.kind == "R":
        return _RES
    if dev.kind == "I":
        return _ISRC
    return _RES


def render_symbol(
    dev: Any,
    origin: Point,
    *,
    mirror: bool = False,
    label: str | None = None,
) -> str:
    sym = symbol_for_device(dev)
    ox, oy = origin.x, origin.y
    body = sym.svg_body
    if mirror:
        body = (
            f'<g transform="translate({ox + sym.width}, {oy}) scale(-1, 1)">'
            f"{sym.svg_body}</g>"
        )
    else:
        body = f'<g transform="translate({ox}, {oy})">{sym.svg_body}</g>'
    name = label or dev.name
    tx = ox + (sym.width // 2) - (len(name) * 3)
    ty = oy + sym.height + 12
    return (
        f"{body}\n"
        f'<text x="{tx}" y="{ty}" fill="#d6deeb" font="10px ui-monospace,monospace">{name}</text>\n'
    )


def terminal_positions(
    dev: Any,
    origin: Point,
    *,
    mirror: bool = False,
) -> dict[str, Point]:
    sym = symbol_for_device(dev)
    if dev.kind == "M":
        d, g, s = mos_anchor_names(dev)
        return {
            dev.nodes[0]: sym.anchor(d, origin, mirror=mirror),
            dev.nodes[1]: sym.anchor(g, origin, mirror=mirror),
            dev.nodes[2]: sym.anchor(s, origin, mirror=mirror),
        }
    p, n = two_term_anchors()
    return {
        dev.nodes[0]: sym.anchor(p, origin, mirror=mirror),
        dev.nodes[1]: sym.anchor(n, origin, mirror=mirror),
    }
