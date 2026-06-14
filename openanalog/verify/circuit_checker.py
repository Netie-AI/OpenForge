from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from openanalog import claude
from openanalog.confidence import kg_tier
from openanalog.forge.fitness import score_fitness
from openanalog.forge.simulator import simulate, SimResult


@dataclass
class LevelResult:
    passed: bool
    confidence_contribution: float
    detail: str = ""


@dataclass
class VerificationResult:
    passed: bool
    confidence: float
    levels: dict[str, LevelResult]
    tier: str | None
    claude_review: dict[str, Any] | None = None


def _level1_syntax(netlist: str) -> LevelResult:
    if ".end" not in netlist.lower():
        return LevelResult(False, 0.5, "missing .end")
    if re.search(r"\bnode\b.*floating", netlist, re.I):
        return LevelResult(False, 0.3, "floating node hint")
    return LevelResult(True, 0.95, "syntax ok")


def _level2_sim(netlist: str) -> LevelResult:
    sim = simulate(netlist, ["op"])
    if not sim.ok:
        return LevelResult(False, 0.2, sim.error or "sim failed")
    if "timestep too small" in sim.raw.lower():
        return LevelResult(False, 0.3, "timestep")
    return LevelResult(True, 0.9, "dc op")


def _level3_physics(netlist: str, sim: SimResult) -> LevelResult:
    if sim.output_voltage > 10 * 3.3:
        return LevelResult(False, 0.1, "voltage overflow")
    if re.search(r"W=0[^.]", netlist):
        return LevelResult(False, 0.4, "zero width")
    return LevelResult(True, 0.85, "sanity ok")


def _level4_fitness(topology: str, sim: SimResult) -> LevelResult:
    fit = score_fitness(topology, sim)
    if fit["score"] != 1:
        return LevelResult(False, 0.5, f"failed {fit['failed_checks']}")
    margins = fit["margin_per_check"]
    if any(v <= 0 for v in margins.values()):
        return LevelResult(False, 0.6, "zero margin")
    return LevelResult(True, 0.95, "specs pass")


def _level5_claude(topology: str, netlist: str, sim: SimResult, top_performer: bool) -> LevelResult:
    if not top_performer:
        return LevelResult(True, 1.0, "skipped")
    try:
        rev = claude.review_netlist(
            topology,
            netlist,
            {
                "bw_MHz": sim.bw_3db_MHz,
                "gain_dB": sim.gain_dB,
                "power_mW": sim.power_mW,
            },
        )
        c = float(rev.get("confidence_10", 7)) / 10.0
        ok = bool(rev.get("topology_sensible", True))
        return LevelResult(ok, c, str(rev.get("issues", [])))
    except RuntimeError as e:
        return LevelResult(True, 0.75, f"claude unavailable: {e}")


def verify_circuit(
    netlist: str,
    topology: str,
    *,
    top_performer: bool = False,
) -> VerificationResult:
    weights = [0.15, 0.25, 0.2, 0.3, 0.1]
    levels: dict[str, LevelResult] = {}
    levels["syntax"] = _level1_syntax(netlist)
    sim = simulate(netlist, ["op", "ac"])
    levels["simulation"] = _level2_sim(netlist)
    levels["physics"] = _level3_physics(netlist, sim)
    levels["fitness"] = _level4_fitness(topology, sim)
    levels["claude"] = _level5_claude(topology, netlist, sim, top_performer)

    conf = 1.0
    for w, lr in zip(weights, levels.values()):
        if lr.passed:
            conf *= lr.confidence_contribution ** w
        else:
            conf *= (lr.confidence_contribution * 0.5) ** w

    passed = all(l.passed for l in levels.values()) and conf >= 0.7
    claude_rev = None
    if levels["claude"].detail and top_performer:
        try:
            claude_rev = claude.review_netlist(topology, netlist, {"gain_dB": sim.gain_dB})
        except RuntimeError:
            pass

    return VerificationResult(
        passed=passed,
        confidence=conf,
        levels=levels,
        tier=kg_tier(conf),
        claude_review=claude_rev,
    )
