from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any

from openanalog.config import ANTHROPIC_API_KEY

MODEL = "claude-sonnet-4-20250514"


def _client():
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set in .env or env.local")
    import anthropic

    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def _parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        return json.loads(m.group())
    return json.loads(text)


def ask_json(system: str, user: str, *, image_path: Path | None = None) -> dict[str, Any]:
    client = _client()
    content: list[dict[str, Any]] = [{"type": "text", "text": user}]
    if image_path and image_path.exists():
        media = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
        b64 = base64.standard_b64encode(image_path.read_bytes()).decode()
        content = [
            {
                "type": "image",
                "source": {"type": "base64", "media_type": media, "data": b64},
            },
            {"type": "text", "text": user},
        ]
    msg = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": content}],
    )
    return _parse_json(msg.content[0].text)


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
    client = _client()
    media = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
    b64 = base64.standard_b64encode(image_path.read_bytes()).decode()
    msg = client.messages.create(
        model=MODEL,
        max_tokens=8192,
        system=(
            "You are an expert analog IC designer. Convert schematic to SPICE netlist.\n"
            "Rules: unique node names (net_001...), ground=0, sky130 W/L, .model NMOS/PMOS, end with .end\n"
            "Output ONLY raw SPICE netlist."
        ),
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": media, "data": b64},
                    },
                    {"type": "text", "text": "Convert to SPICE netlist."},
                ],
            }
        ],
    )
    return msg.content[0].text.strip()


def review_netlist(circuit_type: str, netlist: str, sim_result: dict[str, Any]) -> dict[str, Any]:
    return ask_json(
        "Review SPICE design. JSON only.",
        (
            f"Circuit type: {circuit_type}\nNetlist:\n{netlist}\n\n"
            f"Simulation:\n{json.dumps(sim_result, indent=2)}\n"
            'Output: {"confidence_10": int, "issues": [str], "topology_sensible": bool}'
        ),
    )
