#!/usr/bin/env python3
"""Convert winners.jsonl to Qwen chat-format finetune.jsonl."""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import tempfile

from openanalog.config import resolve_ngspice_cmd
from openanalog.forge.simulator import circuit_only_netlist

SYSTEM = (
    "You are an analog IC design assistant. Given a specification, "
    "output a valid ngspice SPICE netlist for a circuit that meets the spec. "
    "Output only the netlist, no explanation."
)

OPTIONAL_SPECS: dict[str, set[str]] = {
    "comparator": {"tfall_ns"},
}

PARSE_ERROR_KEYS = (
    "syntax error",
    "undefined node",
    "no such file",
    "fatal error",
    "unable to find definition of model",
)


def spec_to_prompt(topology: str, measured_specs: dict, params: dict) -> str:
    spec_lines = []
    for k, v in measured_specs.items():
        if v is not None:
            spec_lines.append(f"  {k}: {v:.4g}")
    return (
        f"Design a {topology} circuit with the following specifications:\n"
        + "\n".join(spec_lines)
        + "\nOutput a complete ngspice SPICE netlist."
    )


def ngspice_parse_ok(netlist: str) -> bool:
    ngspice = resolve_ngspice_cmd()
    if not ngspice:
        return True
    deck = circuit_only_netlist(netlist)
    if ".end" not in deck.lower():
        return False
    with tempfile.NamedTemporaryFile(mode="w", suffix=".sp", delete=False) as fh:
        fh.write(deck)
        tmp = fh.name
    try:
        result = subprocess.run(
            [*ngspice, "-b", tmp],
            capture_output=True,
            text=True,
            timeout=10,
        )
    finally:
        os.unlink(tmp)
    stderr = (result.stderr or "").lower()
    return not any(k in stderr for k in PARSE_ERROR_KEYS)


def main() -> None:
    winners_path = pathlib.Path("data/training/winners.jsonl")
    out_path = pathlib.Path("data/training/finetune.jsonl")

    winners = [
        json.loads(line)
        for line in winners_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    skipped = {"short_netlist": 0, "required_none": 0, "parse_fail": 0}
    out = []
    for w in winners:
        raw = w.get("netlist") or ""
        if not raw or len(raw) < 200:
            skipped["short_netlist"] += 1
            continue
        optional = OPTIONAL_SPECS.get(w["topology"], set())
        specs = w.get("measured_specs", {})
        if any(v is None for k, v in specs.items() if k not in optional):
            skipped["required_none"] += 1
            continue
        netlist = circuit_only_netlist(raw)
        if not ngspice_parse_ok(netlist):
            skipped["parse_fail"] += 1
            continue
        out.append(
            {
                "messages": [
                    {"role": "system", "content": SYSTEM},
                    {
                        "role": "user",
                        "content": spec_to_prompt(
                            w["topology"],
                            w.get("measured_specs", {}),
                            w.get("params", {}),
                        ),
                    },
                    {"role": "assistant", "content": netlist},
                ]
            }
        )

    out_path.write_text(
        "\n".join(json.dumps(r) for r in out) + ("\n" if out else ""),
        encoding="utf-8",
    )
    print(f"Wrote {len(out)} training examples to {out_path}")
    if any(skipped.values()):
        print(f"Skipped: {skipped}")


if __name__ == "__main__":
    main()
