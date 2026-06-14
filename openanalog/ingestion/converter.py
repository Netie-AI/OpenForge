"""Masala / AnalogGenie parenthesis dialect → ngspice-flat converter (Phase 2b)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from openanalog.sim.models import BUNDLED_MODELS, NMOS, PMOS

# AnalogGenie standard cells (converted to ngspice-flat with bundled models).
_ANALOGGENIE_CELLS = """
.subckt INVERTER A Q VDD VSS
M_INV_P Q A VDD VDD {pmos} W=10u L=1u
M_INV_N Q A 0 0 {nmos} W=5u L=1u
.ends INVERTER

.subckt TRANSMISSION_GATE A B C VDD VSS
M_TG_P A TG_INT B VDD {pmos} W=20u L=1u
M_TG_N A C B 0 {nmos} W=10u L=1u
X_TG_INV C TG_INT VDD 0 INVERTER
.ends TRANSMISSION_GATE

.subckt NAND A B Q VDD VSS
M_NAND_P1 Q B VDD VDD {pmos} W=10u L=1u
M_NAND_P0 Q A VDD VDD {pmos} W=10u L=1u
M_NAND_N3 TG_NAND B 0 0 {nmos} W=5u L=1u
M_NAND_N2 Q A TG_NAND 0 {nmos} W=5u L=1u
.ends NAND

.subckt NOR A B Q VDD VSS
M_NOR_P1 Q A TG_NOR VDD {pmos} W=10u L=1u
M_NOR_P0 TG_NOR B VDD VDD {pmos} W=10u L=1u
M_NOR_N3 Q B 0 0 {nmos} W=5u L=1u
M_NOR_N2 Q A 0 0 {nmos} W=5u L=1u
.ends NOR
""".format(pmos=PMOS, nmos=NMOS)

_KNOWN_SUBCKTS = frozenset(
    {"INVERTER", "TRANSMISSION_GATE", "NAND", "NOR", "XOR", "PFD"}
)

_PAREN_LINE_RE = re.compile(
    r"^\s*([A-Za-z]\w*)\s+\(([^)]+)\)\s+(\w+)(.*)$"
)
_SUBCKT_RE = re.compile(r"^\s*\.?subckt\s+(\w+)", re.I)
_ENDS_RE = re.compile(r"^\s*\.?ends\b", re.I)
_COMMENT_RE = re.compile(r"^\s*//")
_ELEMENT_HEAD_RE = re.compile(r"^([A-Za-z]\w*)", re.I)

_MODEL_MAP = {
    "nmos4": NMOS,
    "pmos4": PMOS,
    "resistor": None,
    "capacitor": None,
    "inductor": None,
    "diode": "DMOD",
}

_DEFAULT_R = "10k"
_DEFAULT_C = "1p"
_DEFAULT_L = "1u"

_GROUND_ALIASES = frozenset({"VSS", "GND", "GROUND", "0"})
_SUPPLY_ALIASES = frozenset({"VDD", "VDD3", "VDD3V3", "VCC"})

_BIAS_NET_RE = re.compile(
    r"^V(?:B\d+|CM\d*|CLK\d*|IN\d*|REF\d*|CONT\d+|OUT\d+|DD\d*)$",
    re.I,
)


@dataclass
class ConversionResult:
    netlist: str
    warnings: list[str] = field(default_factory=list)
    converted: bool = False
    original_dialect: str = "unknown"


def _normalize_net(name: str) -> str:
    n = name.strip()
    upper = n.upper()
    if upper in _GROUND_ALIASES:
        return "0"
    if upper in _SUPPLY_ALIASES:
        return "vdd"
    return n


def _split_nodes(nodes_blob: str) -> list[str]:
    return [_normalize_net(x) for x in nodes_blob.split()]


def _unique_element_name(name: str, used: set[str], warnings: list[str]) -> str:
    """Masala/AnalogGenie netlists often reuse device names — rename duplicates."""
    base = name
    candidate = name
    n = 1
    while candidate.lower() in used:
        candidate = f"{base}_{n}"
        n += 1
    if candidate != name:
        warnings.append(f"renamed duplicate device {name} → {candidate}")
    used.add(candidate.lower())
    return candidate


def _convert_paren_line(
    name: str,
    nodes_blob: str,
    token: str,
    tail: str = "",
) -> tuple[str | None, str | None]:
    nodes = _split_nodes(nodes_blob)
    mapped = _MODEL_MAP.get(token.lower(), token)
    extra = tail.strip()

    if token.lower() in ("nmos4", "pmos4"):
        if len(nodes) != 4:
            return None, f"{name}: expected 4 MOSFET nodes, got {len(nodes)}"
        d, g, s, b = nodes
        params = extra or "W=10u L=1u"
        return f"{name} {d} {g} {s} {b} {mapped} {params}", None

    if token.lower() == "resistor":
        if len(nodes) != 2:
            return None, f"{name}: resistor needs 2 nodes"
        return f"{name} {nodes[0]} {nodes[1]} {_DEFAULT_R}", None

    if token.lower() == "capacitor":
        if len(nodes) != 2:
            return None, f"{name}: capacitor needs 2 nodes"
        return f"{name} {nodes[0]} {nodes[1]} {_DEFAULT_C}", None

    if token.lower() == "inductor":
        if len(nodes) != 2:
            return None, f"{name}: inductor needs 2 nodes"
        return f"{name} {nodes[0]} {nodes[1]} {_DEFAULT_L}", None

    if token.lower() in ("npn", "pnp"):
        if len(nodes) != 3:
            return None, f"{name}: BJT needs 3 nodes (c b e)"
        return None, f"{name}: {token} BJT model not bundled — skipped"

    if token in _KNOWN_SUBCKTS or token.isupper():
        inst = ("X" + name[1:]) if name.upper().startswith("I") else f"X_{name}"
        return f"{inst} {' '.join(nodes)} {token}", None

    return None, f"{name}: unknown parenthesis token '{token}'"


def _convert_body_line(
    line: str,
    warnings: list[str],
    used_names: set[str],
) -> str | None:
    stripped = line.strip()
    if not stripped or _COMMENT_RE.match(stripped):
        return None

    m = _PAREN_LINE_RE.match(stripped)
    if m:
        raw_name = m.group(1)
        name = _unique_element_name(raw_name, used_names, warnings)
        converted, warn = _convert_paren_line(
            name, m.group(2), m.group(3), m.group(4)
        )
        if warn:
            warnings.append(warn)
        return converted

    if _SUBCKT_RE.match(stripped):
        return re.sub(r"^\s*\.?subckt", ".subckt", stripped, flags=re.I)

    if _ENDS_RE.match(stripped):
        return re.sub(r"^\s*\.?ends\b.*", ".ends", stripped, flags=re.I)

    parts = stripped.split()
    if parts and parts[0][0].upper() in "MRCVILXQ" and len(parts) >= 3:
        head = _unique_element_name(parts[0], used_names, warnings)
        if head[0].upper() == "M" and len(parts) >= 6:
            tail = parts[5:]
            parts = [head] + [_normalize_net(p) for p in parts[1:5]] + tail
        elif head[0].upper() in "RCL" and len(parts) >= 3:
            parts = [head, _normalize_net(parts[1]), _normalize_net(parts[2])] + parts[3:]
        else:
            parts[0] = head
        return " ".join(parts)

    if stripped.lower().startswith((".include", ".model", ".param", ".global", ".title")):
        return stripped

    if stripped.startswith("*"):
        return stripped

    warnings.append(f"unconverted line: {stripped[:80]}")
    return None


def convert_to_ngspice_flat(netlist: str) -> ConversionResult:
    """
    Convert Masala/AnalogGenie parenthesis syntax to ngspice-flat.

    Unknown lines are recorded in ``warnings`` — never silently dropped without trace.
    """
    from openanalog.ingestion.dialect import detect_dialect

    dialect = detect_dialect(netlist)
    if dialect != "masala-paren":
        return ConversionResult(
            netlist=netlist,
            converted=False,
            original_dialect=dialect,
        )

    warnings: list[str] = []
    out_lines: list[str] = []
    used_names: set[str] = set()
    defined_subckts: set[str] = set()
    referenced_subckts: set[str] = set()

    for raw in netlist.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        if _COMMENT_RE.match(stripped):
            continue

        sm = _SUBCKT_RE.match(stripped)
        if sm:
            defined_subckts.add(sm.group(1).upper())

        m = _PAREN_LINE_RE.match(stripped)
        if m and (m.group(3) in _KNOWN_SUBCKTS or m.group(3).isupper()):
            referenced_subckts.add(m.group(3).upper())

        converted = _convert_body_line(raw, warnings, used_names)
        if converted:
            out_lines.append(converted)

    missing = referenced_subckts - defined_subckts
    if missing:
        for cell in sorted(missing):
            if cell in {"INVERTER", "TRANSMISSION_GATE", "NAND", "NOR"}:
                warnings.append(f"injected bundled subckt {cell}")
            else:
                warnings.append(f"subckt {cell} referenced but not defined — may fail sim")

    body = "\n".join(out_lines)
    if missing & {"INVERTER", "TRANSMISSION_GATE", "NAND", "NOR"}:
        body = _ANALOGGENIE_CELLS.strip() + "\n" + body

    if ".end" not in body.lower():
        body += "\n.end\n"

    return ConversionResult(
        netlist=body,
        warnings=warnings,
        converted=True,
        original_dialect=dialect,
    )


def _collect_bias_nets(netlist: str) -> list[str]:
    nets: set[str] = set()
    for raw in netlist.splitlines():
        for token in re.findall(r"\b([A-Za-z_]\w*)\b", raw):
            if _BIAS_NET_RE.match(token):
                nets.add(_normalize_net(token))
    return sorted(n for n in nets if n not in ("0", "vdd"))


def _collect_circuit_nets(netlist: str) -> set[str]:
    """Nets referenced on device lines (excluding models/directives)."""
    nets: set[str] = set()
    for raw in netlist.splitlines():
        line = raw.strip()
        if not line or line.startswith(("*", ".")):
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        head = parts[0][0].upper()
        if head == "M" and len(parts) >= 6:
            for tok in parts[1:5]:
                nets.add(tok)
        elif head in "RCL" and len(parts) >= 3:
            nets.add(parts[1])
            nets.add(parts[2])
        elif head == "D" and len(parts) >= 3:
            nets.add(parts[1])
            nets.add(parts[2])
        elif head == "X" and len(parts) >= 3:
            for tok in parts[1:-1]:
                nets.add(tok)
    return nets


def _driven_nets(deck: str) -> set[str]:
    driven = {"0", "vdd", "gnd"}
    for raw in deck.splitlines():
        m = re.match(r"^\s*V(\w+)\s+(\S+)\s+(\S+)", raw, re.I)
        if m:
            driven.add(m.group(2).lower())
            driven.add(m.group(3).lower())
    return driven


def _floating_pulldowns(netlist: str, driven: set[str]) -> list[str]:
    """1GΩ bleed resistors on nets without explicit DC excitation."""
    lines: list[str] = []
    idx = 0
    for net in sorted(_collect_circuit_nets(netlist), key=str.lower):
        if net.lower() in driven or net.lower() in ("0", "vdd", "gnd"):
            continue
        idx += 1
        lines.append(f"RFP{idx} {net} 0 1G")
    return lines


def prepare_seed_deck(netlist: str) -> str:
    """Wrap flat netlist with models, supply rails, bias stubs, and DC helpers for .op."""
    text = netlist.strip()
    needs_vdd = re.search(r"\bvdd\b", text, re.I) is not None

    stubs: list[str] = []
    if needs_vdd:
        stubs.append("VDD_SUPPLY vdd 0 DC 1.8")

    for i, net in enumerate(_collect_bias_nets(text)):
        val = "1.8" if "clk" in net.lower() else "0.9"
        stubs.append(f"VBIAS{i + 1} {net} 0 DC {val}")

    parts = ["* openforge seed deck", BUNDLED_MODELS.strip()]
    if "DMOD" in text:
        parts.append(".model DMOD D (IS=1e-14 N=1 RS=10)")
    parts.extend(stubs)
    parts.append(text)

    partial = "\n".join(parts)
    driven = _driven_nets(partial)
    pulldowns = _floating_pulldowns(text, driven)
    if pulldowns:
        parts.extend(pulldowns)

    if needs_vdd:
        parts.append(".ic v(vdd)=1.8")
    parts.append(".ic v(0)=0")

    if ".end" not in text.lower():
        parts.append(".end")
    return "\n".join(parts) + "\n"


_UNIT_MULT: dict[str, float] = {
    "f": 1e-15,
    "p": 1e-12,
    "n": 1e-9,
    "u": 1e-6,
    "m": 1e-3,
    "k": 1e3,
    "meg": 1e6,
    "g": 1e9,
    "": 1.0,
}

_PARAM_LINE_RE = re.compile(r"\.param\s+(\w+)=(\S+)", re.I)
_WL_PAIR_RE = re.compile(
    r"W=([\d.eE+-]+)([munpf]?)\s+L=([\d.eE+-]+)([munpf]?)",
    re.I,
)
_IREF_LINE_RE = re.compile(
    r"^\s*I(\w+)\s+\S+\s+\S+\s+\{?([\d.eE+-]+)([munpf]?)\}?",
    re.I | re.M,
)


def _parse_spice_value(raw: str) -> float:
    raw = raw.strip().lower().replace("{", "").replace("}", "")
    m = re.match(r"([\d.e+-]+)([munpfk]?)?", raw)
    if not m:
        raise ValueError(f"bad spice value: {raw}")
    val = float(m.group(1))
    unit = m.group(2) or ""
    return val * _UNIT_MULT.get(unit, 1.0)


def extract_params(netlist: str) -> dict[str, float]:
    """
    Pull W/L, .param, and bias current hints from a converted seed netlist.

    Used by forge to seed parameter search — not netlist structure.
    """
    hints: dict[str, float] = {}
    text = netlist or ""

    for m in _PARAM_LINE_RE.finditer(text):
        key = m.group(1)
        try:
            hints[key] = _parse_spice_value(m.group(2))
        except ValueError:
            continue

    wl_idx = 1
    for m in _WL_PAIR_RE.finditer(text):
        try:
            w = _parse_spice_value(m.group(1) + (m.group(2) or ""))
            l_val = _parse_spice_value(m.group(3) + (m.group(4) or ""))
        except ValueError:
            continue
        w_key = f"W{wl_idx}"
        l_key = f"L{wl_idx}"
        hints.setdefault(w_key, w)
        hints.setdefault(l_key, l_val)
        hints.setdefault("Wn" if wl_idx == 1 else f"W{wl_idx}", w)
        hints.setdefault("Wp", w)
        hints.setdefault("len_n", l_val)
        hints.setdefault("len_p", l_val)
        wl_idx += 1

    for m in _IREF_LINE_RE.finditer(text):
        try:
            hints.setdefault("Iref", _parse_spice_value(m.group(2) + (m.group(3) or "")))
        except ValueError:
            continue

    alias = {
        "IREF": "Iref",
        "WN": "Wn",
        "WP": "Wp",
        "LENN": "len_n",
        "LENP": "len_p",
        "CC": "Cc",
    }
    for src, dst in alias.items():
        if src in hints and dst not in hints:
            hints[dst] = hints[src]

    return hints


def normalize_for_forge(netlist: str) -> tuple[str, list[str], str]:
    """Detect → convert → return flat netlist for storage."""
    from openanalog.ingestion.dialect import detect_dialect

    dialect = detect_dialect(netlist)
    if dialect == "masala-paren":
        result = convert_to_ngspice_flat(netlist)
        return result.netlist, result.warnings, dialect
    return netlist, [], dialect
