"""Heuristic topology inference for converted seed netlists."""

from __future__ import annotations

import re

_BENCH_TOPOLOGIES = frozenset({"opamp", "comparator", "switch", "charge_pump"})

_MOS_RE = re.compile(
    r"^\s*([Mm]\w+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+",
    re.MULTILINE,
)
_CAP_RE = re.compile(r"^\s*C\w+\s+(\S+)\s+(\S+)", re.MULTILINE)
_DIODE_RE = re.compile(r"^\s*D\w+\s+(\S+)\s+(\S+)", re.MULTILINE)
_SUBCKT_INST_RE = re.compile(r"^\s*X\w+\s+.*\s+(TRANSMISSION_GATE|INVERTER)\s*$", re.MULTILINE | re.I)


def bench_topologies() -> frozenset[str]:
    return _BENCH_TOPOLOGIES


def infer_topology(netlist: str) -> str:
    """
    Map a flat netlist to a registered bench topology name.

    Heuristic — ~70% on amplifier-class seeds is sufficient; unknown seeds
    are not awarded fitness=1 on the sim_ok gate.
    """
    text = netlist or ""
    lo = text.lower()

    if _SUBCKT_INST_RE.search(text) or lo.count("transmission_gate") >= 1:
        return "switch"

    diodes = len(_DIODE_RE.findall(text))
    caps = len(_CAP_RE.findall(text))
    if diodes >= 2 and caps >= 2 and re.search(r"vclk|clk\d", lo):
        return "charge_pump"

    nmos_lines = []
    for m in _MOS_RE.finditer(text):
        dev, d, g, s, b = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
        if "pmos" in m.group(0).lower() or b.lower() in ("vdd", "vdd3"):
            continue
        nmos_lines.append((dev, d, g, s, b))

    tail_groups: dict[str, list[tuple[str, str, str]]] = {}
    for _dev, d, g, s, _b in nmos_lines:
        tail_groups.setdefault(s.lower(), []).append((d, g, s))

    diff_pair = False
    for _tail, devices in tail_groups.items():
        if len(devices) >= 2:
            gates = {g.lower() for _d, g, _s in devices}
            if len(gates) >= 2:
                diff_pair = True
                break

    if diff_pair:
        miller = bool(re.search(r"^\s*C\w+\s+\S+\s+\S+", text, re.MULTILINE))
        if re.search(r"vclk\d|vclk\b", lo) and not miller:
            return "comparator"
        return "opamp"

    if caps >= 2 and re.search(r"pump|dickson|flying", lo):
        return "charge_pump"

    return "unknown"


def resolve_forge_topology(netlist: str, seed_circuit_type: str | None = None) -> str:
    """Infer from netlist; optionally map seed labels like amplifier → opamp."""
    inferred = infer_topology(netlist)
    if inferred != "unknown":
        return inferred

    label = (seed_circuit_type or "unknown").lower()
    if label in _BENCH_TOPOLOGIES:
        return label
    if label in ("amplifier", "diff_amp", "ota"):
        return "opamp"
    if label == "analog_switch":
        return "switch"
    return "unknown"
