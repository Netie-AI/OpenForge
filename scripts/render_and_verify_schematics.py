#!/usr/bin/env python3
"""Re-render sample schematic SVGs and verify terminal/wire connectivity."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from openanalog.eda.netlist_graph import parse_spice_devices
from openanalog.eda.schematic_connectivity import anchor_wire_diffs, verify_schematic_connectivity
from openanalog.eda.schematic_layout import render_schematic_svg
from openanalog.interface.designer import design

CASES = (
    (
        "logs/schematic_0.7_two_stage_miller_opamp.svg",
        dict(text="RS722 high precision low offset op-amp", budget=40, use_llm=False),
    ),
    (
        "logs/schematic_0.7_diff_pair_comparator.svg",
        dict(category="comparator", inline_spec="tp<1us vos<5mV iq<10uA", budget=40, use_llm=False),
    ),
)


def main() -> int:
    logs = ROOT / "logs"
    logs.mkdir(exist_ok=True)
    failed = False

    for rel_path, kwargs in CASES:
        out = ROOT / rel_path
        result = design(**kwargs)
        devices = parse_spice_devices(result["netlist"])
        svg = render_schematic_svg(devices, result)
        out.write_text(svg, encoding="utf-8")
        print(f"wrote {out.relative_to(ROOT)} ({len(svg)} bytes)")

        diffs = anchor_wire_diffs(devices, result)
        errors = verify_schematic_connectivity(devices, result)
        if diffs:
            failed = True
            print(f"  anchor/wire diffs ({len(diffs)}):")
            for d in diffs[:10]:
                print(f"    {d}")
        if errors:
            failed = True
            print(f"  connectivity errors ({len(errors)}):")
            for e in errors[:10]:
                print(f"    {e}")
        if not diffs and not errors:
            print("  connectivity OK")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
