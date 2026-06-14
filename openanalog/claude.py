from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openanalog import llm
from openanalog.config import OPENFORGE_CLAUDE_MODEL

# Backward-compatible default model name
MODEL = OPENFORGE_CLAUDE_MODEL


def ask_json(system: str, user: str, *, image_path: Path | None = None) -> dict[str, Any]:
    """Delegate to multi-provider router; prefer Anthropic when available."""
    data = llm.ask_json(system, user, provider="anthropic", image_path=image_path)
    data.pop("_llm_provider", None)
    data.pop("_llm_model", None)
    return data


def reexamine_ambiguous(
    task: str,
    payload: dict[str, Any],
    *,
    image_path: Path | None = None,
) -> dict[str, Any]:
    """Chain-of-thought re-examination for 0.5–0.7 confidence zone."""
    system = (
        "You are an expert analog IC designer reviewing uncertain extractions. "
        "Think step by step, then output ONLY valid JSON with keys: "
        "confidence (0-1 float), revised (object or string as appropriate), "
        "issues (string array), accept (bool)."
    )
    user = (
        f"Task: {task}\n"
        f"Current data:\n{json.dumps(payload, indent=2)}\n"
        "Re-evaluate carefully. If accept=true, confidence should reflect your certainty."
    )
    return ask_json(system, user, image_path=image_path)


def classify_schematic(image_path: Path) -> dict[str, Any]:
    return ask_json(
        "Respond with JSON only.",
        (
            "Is this image a circuit schematic showing electronic components "
            "(transistors, capacitors, resistors, op-amps, wires)? "
            'Answer JSON: {"is_schematic": bool, "confidence": float, '
            '"circuit_type": str, "components_visible": [str]}'
        ),
        image_path=image_path,
    )


def extract_nearby_params(context: str) -> dict[str, Any]:
    return ask_json(
        "Extract circuit parameters from text. JSON only.",
        (
            "Extract all circuit parameters mentioned near this schematic:\n"
            f"{context}\n"
            'Output JSON: {"params": {"name": "value_with_unit"}, '
            '"specs": {"metric": "target"}}'
        ),
    )


def schematic_to_spice(image_path: Path) -> str:
    text, _, _ = llm.ask_text(
        (
            "You are an expert analog IC designer. Convert schematic to SPICE netlist.\n"
            "Rules: unique node names (net_001...), ground=0, sky130 W/L, .model NMOS/PMOS, end with .end\n"
            "Output ONLY raw SPICE netlist."
        ),
        "Convert to SPICE netlist.",
        provider="anthropic",
        image_path=image_path,
    )
    return text.strip()


def review_netlist(circuit_type: str, netlist: str, sim_result: dict[str, Any]) -> dict[str, Any]:
    return ask_json(
        "Review SPICE design. JSON only.",
        (
            f"Circuit type: {circuit_type}\nNetlist:\n{netlist}\n\n"
            f"Simulation:\n{json.dumps(sim_result, indent=2)}\n"
            'Output: {"confidence_10": int, "issues": [str], "topology_sensible": bool}'
        ),
    )
