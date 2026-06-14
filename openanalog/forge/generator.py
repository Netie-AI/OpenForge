from __future__ import annotations

import math
import random
import re
from enum import Enum


class MutationMode(str, Enum):
    RANDOM = "random"
    DIRECTED = "directed"
    CROSSOVER = "crossover"


RANGES = {
    "nmos_w": (0.5e-6, 10e-6),
    "nmos_l": (0.15e-6, 2e-6),
    "pmos_w": (1e-6, 20e-6),
    "pmos_l": (0.15e-6, 2e-6),
    "r": (1e3, 1e6),
    "c": (10e-15, 10e-12),
    "i": (1e-6, 500e-6),
    "vdd": (1.2, 3.3),
}


def _log_uniform(lo: float, hi: float) -> float:
    return math.exp(random.uniform(math.log(lo), math.log(hi)))


def _fmt_si(value: float, kind: str) -> str:
    if kind in ("w", "l"):
        if value >= 1e-6:
            return f"{value * 1e6:.3g}u"
        return f"{value * 1e9:.3g}n"
    if kind == "r":
        if value >= 1e6:
            return f"{value / 1e6:.3g}M"
        if value >= 1e3:
            return f"{value / 1e3:.3g}k"
        return f"{value:.3g}"
    if kind == "c":
        if value >= 1e-12:
            return f"{value * 1e12:.3g}p"
        if value >= 1e-9:
            return f"{value * 1e9:.3g}n"
        return f"{value * 1e15:.3g}f"
    return f"{value:.3g}"


def electrical_rules_ok(netlist: str) -> tuple[bool, str]:
    if "node" in netlist.lower() and "floating" in netlist.lower():
        return False, "floating nodes"
    vdd = re.search(r"V(?:DD|cc)\s+(\S+)\s+0\s+DC\s+([\d.]+)", netlist, re.I)
    if vdd and float(vdd.group(2)) <= 0:
        return False, "VDD <= VSS"
    for m in re.finditer(r"\bW=([\d.]+)([unpf]?)", netlist, re.I):
        w = float(m.group(1))
        u = (m.group(2) or "u").lower()
        scale = {"u": 1e-6, "n": 1e-9, "p": 1e-12, "f": 1e-15}.get(u, 1)
        w_m = w * scale
        if w_m < RANGES["nmos_w"][0] or w_m > RANGES["pmos_w"][1] * 2:
            return False, "W out of range"
    return True, ""


def mutate_netlist(
    netlist: str,
    mode: MutationMode = MutationMode.RANDOM,
    *,
    failed_checks: list[str] | None = None,
    parent_b: str | None = None,
) -> str:
    out = netlist
    failed = failed_checks or []

    def repl_w(match: re.Match[str]) -> str:
        w = _log_uniform(*RANGES["nmos_w"])
        return f"W={_fmt_si(w, 'w')}"

    def repl_l(match: re.Match[str]) -> str:
        l = _log_uniform(*RANGES["nmos_l"])
        return f"L={_fmt_si(l, 'l')}"

    if mode == MutationMode.CROSSOVER and parent_b:
        lines_a = netlist.splitlines()
        lines_b = parent_b.splitlines()
        out = "\n".join(
            b if i % 2 and i < len(lines_b) else a
            for i, (a, b) in enumerate(zip(lines_a, lines_b + lines_a))
        )

    if mode == MutationMode.DIRECTED:
        if "bw" in failed:
            out = re.sub(r"W=([\d.]+[unp]?)", repl_w, out, count=2)
        if "gain" in failed:
            out = re.sub(r"L=([\d.]+[unp]?)", repl_l, out, count=1)
        if "power" in failed:
            out = re.sub(
                r"(I\w+\s+\S+\s+\S+\s+DC\s+)([\d.]+)([un]?)",
                lambda m: f"{m.group(1)}{_fmt_si(_log_uniform(*RANGES['i']), 'i')}",
                out,
                count=1,
            )
        if "PM" in failed or "pm" in failed:
            out = re.sub(r"C(\d+)", lambda m: f"C{m.group(1)}", out)
        if "ripple" in failed:
            out = re.sub(r"C(\d+)\s+(\S+)\s+(\S+)\s+([\d.]+[pf]?)", repl_w, out, count=2)

    if mode == MutationMode.RANDOM or mode == MutationMode.DIRECTED:
        out = re.sub(r"W=([\d.]+[unp]?)", repl_w, out)
        out = re.sub(r"L=([\d.]+[unp]?)", repl_l, out)
        out = re.sub(
            r"(\d+\.?\d*)([kKmM]?)\s*(?=#.*[Rr]es|\s*$)",
            lambda m: _fmt_si(_log_uniform(*RANGES["r"]), "r"),
            out,
            count=0,
        )

    ok, reason = electrical_rules_ok(out)
    if not ok:
        raise ValueError(f"Electrical rule violation: {reason}")
    return out
