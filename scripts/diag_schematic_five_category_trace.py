"""Five-category schematic invariant trace (render-path, post scorer 0.9).

Reviewer gate: for each dev-mode category, from raw SVG + routed geometry report:
  1. active transistor body slices (transverse, same-net included)
  2. cross-net collinear overlaps (horizontal + vertical)
  3. false junction dots (dot on foreign net tracks)

Uses design() + render_schematic_svg — same path as browser. Writes SVG artifacts
to logs/schematic_0.9_<category>.svg.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from openanalog.eda.netlist_graph import parse_spice_devices
from openanalog.eda.schematic_connectivity import (
    anchor_wire_diffs,
    collinear_net_overlap_errors,
    false_junction_dot_errors,
    hop_centers,
    junction_points,
    verify_schematic_connectivity,
)
from openanalog.eda.schematic_geometry import Segment, find_bad_crossings, find_collinear_overlaps
from openanalog.eda.schematic_layout import (
    _collect_net_points,
    _device_boxes,
    _segments_for_score,
    all_rail_riser_segments,
    build_schematic_layout,
    render_schematic_svg,
)
from openanalog.eda.schematic_router import route_nets
from openanalog.forge.spec_envelopes import DEV_MODE_SPECS
from openanalog.interface.designer import design

CASES = (
    ("opamp", dict(text="RS722 high precision low offset op-amp", budget=40, use_llm=False)),
    ("comparator", dict(category="comparator", inline_spec=DEV_MODE_SPECS["comparator"], budget=40, use_llm=False)),
    ("switch", dict(category="switch", inline_spec=DEV_MODE_SPECS["switch"], budget=40, use_llm=False)),
    ("charge_pump", dict(category="charge_pump", inline_spec=DEV_MODE_SPECS["charge_pump"], budget=40, use_llm=False)),
    ("vref", dict(category="vref", inline_spec="vref=1.2V line_reg<5mV tempco<100ppm iq<200uA", budget=40, use_llm=False)),
)


def trace_category(name: str, kwargs: dict) -> bool:
    result = design(**kwargs)
    devices = parse_spice_devices(result["netlist"])
    svg = render_schematic_svg(devices, result)
    out = ROOT / "logs" / f"schematic_0.9_{name}.svg"
    out.write_text(svg, encoding="utf-8")

    layout = build_schematic_layout(devices, result)
    routed = route_nets(layout.placed)
    boxes = _device_boxes(layout.placed)
    segments, junctions = _segments_for_score(layout)

    bad = find_bad_crossings(segments, junctions, boxes)
    active_slices = [
        c for c in bad
        if c.reason.startswith("wire-through-device")
        and any(b.name == c.reason.split(":", 1)[1] and b.is_active for b in boxes)
    ]

    sig = [Segment(s.x1, s.y1, s.x2, s.y2, s.net, s.kind) for s in routed.segments if s.kind == "wire"]
    nets = _collect_net_points(layout.placed)
    gnd = all_rail_riser_segments(layout.placed, nets, layout.height, routed.segments)
    collinear = find_collinear_overlaps(sig + gnd)

    collinear_errs = collinear_net_overlap_errors(devices, result)
    false_dots = false_junction_dot_errors(devices, result)
    dots = junction_points(svg)
    hops = hop_centers(svg)
    floating = anchor_wire_diffs(devices, result)
    conn_errs = verify_schematic_connectivity(devices, result)
    float_terminals = [e for e in conn_errs if "not on any wire" in e or "anchor" in e]

    ok = (
        not active_slices
        and not collinear
        and not false_dots
        and not floating
        and not float_terminals
    )

    print(f"\n=== {name} topology={result.get('topology', '?')} variant={layout.variant} ===")
    print(f"  artifact: {out.relative_to(ROOT)}")
    print(f"  active-body slices: {len(active_slices)}")
    for c in active_slices:
        print(f"    {c.reason} net={c.a.net} ({c.a.x1},{c.a.y1})->({c.a.x2},{c.a.y2})")
    print(f"  cross-net collinear (H+V): {len(collinear)}")
    for a, b, hit in collinear:
        axis = "y" if hit[0] == 0 else "x"
        print(f"    {a.net} vs {b.net} {axis}={hit[1]} [{hit[2]},{hit[3]}]")
    for e in collinear_errs[:5]:
        print(f"    connectivity: {e}")
    print(f"  junction dots: {len(dots)}  wire-hops: {len(hops)}")
    print(f"  false junction dots: {len(false_dots)}")
    for e in false_dots:
        print(f"    {e}")
    print(f"  floating pins (anchor): {len(floating)}")
    for e in floating[:12]:
        print(f"    {e}")
    if len(floating) > 12:
        print(f"    ... +{len(floating) - 12} more")
    print(f"  connectivity floating terminals: {len(float_terminals)}")
    for e in float_terminals[:8]:
        print(f"    {e}")
    print(f"  floorplan_defined: {layout.floorplan_defined}")
    print(f"  GATE: {'PASS' if ok else 'FAIL'}")
    return ok


def main() -> int:
    (ROOT / "logs").mkdir(exist_ok=True)
    results = {name: trace_category(name, kw) for name, kw in CASES}
    all_ok = all(results.values())
    print("\n=== SUMMARY ===")
    for name, ok in results.items():
        print(f"  {name}: {'PASS' if ok else 'FAIL'}")
    print(f"ALL_FIVE_CATEGORIES_OK={all_ok}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
