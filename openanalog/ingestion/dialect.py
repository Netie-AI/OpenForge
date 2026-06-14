"""SPICE netlist dialect detection for seed ingestion (Phase 2a)."""

from __future__ import annotations

import re
from typing import Literal

Dialect = Literal["ngspice-flat", "masala-paren", "unknown"]

# Masala / AnalogGenie:  Name (n1 n2 ...) model_or_cell
_PAREN_DEVICE_RE = re.compile(
    r"^\s*([A-Za-z]\w*)\s+\(([^)]+)\)\s+(\w+)",
    re.MULTILINE,
)

# Standard ngspice MOSFET: Mname d g s b model [params] — nodes are never parenthesized.
_FLAT_MOSFET_RE = re.compile(
    r"^\s*[Mm]\w+\s+(?!\()[^\s(]+\s+(?!\()[^\s(]+\s+(?!\()[^\s(]+\s+(?!\()[^\s(]+\s+\S+",
    re.MULTILINE,
)

# Standard two-terminal passives / sources without parenthesis nodes.
_FLAT_PASSIVE_RE = re.compile(
    r"^\s*([RrCcLlVvIi])\w+\s+(?!\()[^\s(]+\s+(?!\()[^\s(]+",
    re.MULTILINE,
)

_MASALA_MODEL_TOKENS = frozenset(
    {
        "nmos4",
        "pmos4",
        "npn",
        "pnp",
        "resistor",
        "capacitor",
        "inductor",
        "diode",
    }
)

_MASALA_CELL_TOKENS = frozenset(
    {"INVERTER", "TRANSMISSION_GATE", "NAND", "NOR", "XOR", "PFD"}
)


def _is_masala_paren_line(token: str) -> bool:
    if token.lower() in _MASALA_MODEL_TOKENS:
        return True
    if token in _MASALA_CELL_TOKENS:
        return True
    # AnalogGenie subckt instance lines use uppercase cell names.
    return token.isupper() and token.isidentifier()


def detect_dialect(netlist: str) -> Dialect:
    """
    Classify a netlist dialect.

    - ``masala-paren``: AnalogGenie / Masala parenthesis device lines
    - ``ngspice-flat``: standard SPICE element lines without parenthesis nodes
    - ``unknown``: empty or unrecognised
    """
    text = (netlist or "").strip()
    if not text:
        return "unknown"

    has_paren_style = False
    for m in _PAREN_DEVICE_RE.finditer(text):
        if _is_masala_paren_line(m.group(3)):
            has_paren_style = True
            break

    if has_paren_style:
        return "masala-paren"

    has_flat_mos = bool(_FLAT_MOSFET_RE.search(text))
    has_flat_passive = bool(_FLAT_PASSIVE_RE.search(text))

    if has_flat_mos or has_flat_passive:
        return "ngspice-flat"

    if _PAREN_DEVICE_RE.search(text):
        return "masala-paren"

    return "unknown"


def dialect_breakdown(netlists: list[str]) -> dict[Dialect, int]:
    """Count dialects across a list of netlist strings."""
    counts: dict[Dialect, int] = {"ngspice-flat": 0, "masala-paren": 0, "unknown": 0}
    for nl in netlists:
        counts[detect_dialect(nl)] += 1
    return counts
