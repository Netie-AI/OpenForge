"""
API netlist generation with prompt + harness engineering.

Use this instead of local LoRA when API keys are available.
The forge sizer (design()) remains the spec-guaranteed path; this module
is for LLM-generated netlists with ngspice repair loops.
"""

from __future__ import annotations

import json
import random
import re
import time
from pathlib import Path
from typing import Any

from openanalog.config import MODEL_SET, TRAINING_DIR
from openanalog.forge.simulator import circuit_only_netlist, validate_syntax
from openanalog.sim.models import BUNDLED_MODELS

WINNERS = TRAINING_DIR / "winners.jsonl"
USAGE_LOG = Path("data/api_usage.jsonl")


def _log_api_call(
    provider: str,
    topology: str,
    syntax_ok: bool,
    repair_attempts: int,
    latency_s: float,
) -> None:
    USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with USAGE_LOG.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "ts": time.time(),
                    "provider": provider,
                    "topology": topology,
                    "syntax_ok": syntax_ok,
                    "repair_attempts": repair_attempts,
                    "latency_s": round(latency_s, 3),
                }
            )
            + "\n"
        )

NETLIST_API_SYSTEM = """You are an expert analog IC designer writing ngspice SPICE netlists.

Rules (strict):
- Output ONLY raw SPICE — no markdown fences, no explanation.
- Include bundled MOSFET models (nmos_ana / pmos_ana) or reference them if already in examples.
- Use unique node names; ground is node 0.
- End with a single .end line.
- Do NOT include .control, .tran, .ac, .op, or .meas blocks — circuit definition only.
- MOSFET lines: Mname drain gate source bulk model W=... L=...
- Include supply (VDD) and bias sources appropriate for the topology.

Topology hints:
- opamp: two-stage Miller compensated, nodes out/gb, Cc between stages
- comparator: diff pair + output stage, measure at vout
- switch: transmission gate or NMOS/PMOS pair, ron at signal path
- ldo: pass device + error amp + feedback divider
- charge_pump: Dickson with bootstrapped NMOS switches, clock phases
"""


def _extract_netlist(text: str) -> str:
    """Pull SPICE from LLM output (strip markdown fences and preamble)."""
    text = text.strip()
    m = re.search(r"```(?:spice|sp)?\s*([\s\S]*?)```", text, re.I)
    if m:
        text = m.group(1).strip()
    for marker in ("* OpenForge", "* openforge", "* LDO", ".model", ".subckt"):
        idx = text.find(marker)
        if idx >= 0:
            text = text[idx:]
            break
    return circuit_only_netlist(text)


def _few_shot_block(topology: str, *, seed: int = 42) -> str:
    """One corpus winner as a spec→netlist example (prompt tuning anchor)."""
    if not WINNERS.exists():
        return ""
    rows = []
    for line in WINNERS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        w = json.loads(line)
        if w.get("topology") == topology:
            rows.append(w)
    if not rows:
        return ""
    rng = random.Random(seed)
    w = rng.choice(rows)
    specs = w.get("measured_specs") or {}
    spec_lines = [f"  {k}: {v:.4g}" for k, v in specs.items() if v is not None]
    netlist = circuit_only_netlist(w.get("netlist") or "")
    preview = netlist[:1200] + ("..." if len(netlist) > 1200 else "")
    return (
        f"\nExample ({topology}):\n"
        f"SPEC:\n" + "\n".join(spec_lines) + "\n"
        f"NETLIST:\n{preview}\n"
    )


def _spec_prompt(topology: str, spec: dict[str, Any]) -> str:
    measured = spec.get("measured_specs") or spec.get("targets") or spec
    if isinstance(measured, dict) and "targets" in spec:
        measured = spec["targets"]
    lines = []
    if isinstance(measured, dict):
        for k, v in measured.items():
            if v is None:
                continue
            val = v.get("value") if isinstance(v, dict) else v
            if val is not None:
                lines.append(f"  {k}: {float(val):.4g}")
    supply = spec.get("supply_V", 5.0)
    return (
        f"Design a {topology} circuit (VDD={supply}V) with specifications:\n"
        + "\n".join(lines)
        + "\n\nOutput a complete ngspice circuit netlist (models + devices + .end only)."
    )


def _ensure_models(netlist: str) -> str:
    """Prepend bundled models if the netlist references nmos_ana/pmos_ana without .model."""
    nl = netlist.lower()
    if ".model" in nl:
        return netlist
    if "nmos_ana" in nl or "pmos_ana" in nl:
        return BUNDLED_MODELS.strip() + "\n" + netlist
    return netlist


def generate_netlist_api(
    spec: dict[str, Any],
    topology: str,
    *,
    provider: str | None = None,
    model: str | None = None,
    few_shot: bool = True,
    few_shot_seed: int = 42,
    _from_repair: bool = False,
) -> dict[str, Any]:
    """
    Generate a circuit netlist via API LLM (OpenRouter/Groq/Anthropic/...).

    Returns dict with netlist, provider, model, and raw text.
    """
    from openanalog import llm

    t0 = time.perf_counter()
    user = _spec_prompt(topology, spec)
    if few_shot:
        user += _few_shot_block(topology, seed=few_shot_seed)

    raw, prov, mdl = llm.ask_text(
        NETLIST_API_SYSTEM,
        user,
        provider=provider,
        model=model,
    )
    netlist = _ensure_models(_extract_netlist(raw))
    result = {
        "netlist": netlist,
        "raw": raw,
        "provider": prov,
        "model": mdl,
        "topology": topology,
        "model_set": MODEL_SET,
    }
    if not _from_repair:
        ok, _ = validate_syntax(netlist)
        _log_api_call(prov, topology, ok, 0, time.perf_counter() - t0)
    return result


def generate_netlist_with_repair(
    spec: dict[str, Any],
    topology: str,
    *,
    provider: str | None = None,
    model: str | None = None,
    max_attempts: int = 3,
    few_shot: bool = True,
) -> dict[str, Any]:
    """
    API netlist generation + ngspice syntax harness (repair loop).

    On parse failure, feeds errors back to the LLM for correction.
    Falls back to last attempt if all repairs fail.
    """
    from openanalog import llm

    t0 = time.perf_counter()
    result = generate_netlist_api(
        spec,
        topology,
        provider=provider,
        model=model,
        few_shot=few_shot,
        _from_repair=True,
    )
    netlist = result["netlist"]
    attempts = [{"netlist": netlist, "ok": False, "warnings": []}]
    repair_calls = 0

    for i in range(max_attempts):
        ok, warnings = validate_syntax(netlist)
        attempts[-1]["ok"] = ok
        attempts[-1]["warnings"] = warnings
        if ok:
            result["netlist"] = netlist
            result["syntax_ok"] = True
            result["attempts"] = attempts
            _log_api_call(
                result.get("provider", provider or "unknown"),
                topology,
                True,
                repair_calls,
                time.perf_counter() - t0,
            )
            return result
        if i + 1 >= max_attempts:
            break
        repair_user = (
            f"The following {topology} SPICE netlist failed ngspice syntax check.\n"
            f"Errors:\n" + "\n".join(f"- {w}" for w in warnings[:8]) + "\n\n"
            f"Broken netlist:\n{netlist}\n\n"
            "Fix the netlist. Output ONLY the corrected SPICE (circuit + .end, no .control)."
        )
        raw, prov, mdl = llm.ask_text(NETLIST_API_SYSTEM, repair_user, provider=provider, model=model)
        repair_calls += 1
        netlist = _ensure_models(_extract_netlist(raw))
        result["provider"] = prov
        result["model"] = mdl
        attempts.append({"netlist": netlist, "ok": False, "warnings": []})

    result["netlist"] = netlist
    result["syntax_ok"] = False
    result["attempts"] = attempts
    _log_api_call(
        result.get("provider", provider or "unknown"),
        topology,
        False,
        repair_calls,
        time.perf_counter() - t0,
    )
    return result
