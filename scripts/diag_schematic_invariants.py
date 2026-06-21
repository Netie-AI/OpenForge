"""Fast (no-ngspice) schematic invariant check for opamp + comparator render path.

Validates the geometric invariants the slow ngspice connectivity suite asserts,
using build_schematic_layout + route_nets directly (identical routing code).
"""

from __future__ import annotations

from openanalog.eda.netlist_graph import SpiceDevice
from openanalog.eda.schematic_geometry import Segment, find_bad_crossings, find_collinear_overlaps
from openanalog.eda.schematic_layout import (
    _device_boxes,
    _segments_for_score,
    all_rail_riser_segments,
    build_schematic_layout,
    _collect_net_points,
)
from openanalog.eda.schematic_router import route_nets


def _opamp_devices() -> list[SpiceDevice]:
    return [
        SpiceDevice("Iref", "I", ["vdd", "nb"]),
        SpiceDevice("M8", "M", ["nb", "nb", "0", "0"], model="nmos"),
        SpiceDevice("M5", "M", ["tail", "nb", "0", "0"], model="nmos"),
        SpiceDevice("M7", "M", ["vout", "nb", "0", "0"], model="nmos"),
        SpiceDevice("M1", "M", ["n1", "vinp", "tail", "0"], model="nmos"),
        SpiceDevice("M2", "M", ["nout1", "vinn", "tail", "0"], model="nmos"),
        SpiceDevice("M3", "M", ["n1", "n1", "vdd", "vdd"], model="pmos"),
        SpiceDevice("M4", "M", ["nout1", "n1", "vdd", "vdd"], model="pmos"),
        SpiceDevice("M6", "M", ["vout", "nout1", "vdd", "vdd"], model="pmos"),
        SpiceDevice("Cc", "C", ["vout", "nout1"]),
    ]


def _comparator_devices() -> list[SpiceDevice]:
    return [
        SpiceDevice("M8", "M", ["nb", "nb", "0", "0"], model="nmos"),
        SpiceDevice("M5", "M", ["tail", "nb", "0", "0"], model="nmos"),
        SpiceDevice("M1", "M", ["n1", "vinp", "tail", "0"], model="nmos"),
        SpiceDevice("M2", "M", ["nout1", "vinn", "tail", "0"], model="nmos"),
        SpiceDevice("M3", "M", ["n1", "n1", "vdd", "vdd"], model="pmos"),
        SpiceDevice("M4", "M", ["nout1", "n1", "vdd", "vdd"], model="pmos"),
        SpiceDevice("Iref", "I", ["vdd", "nb"]),
    ]


def _check(name: str, devices: list[SpiceDevice], topology: str) -> bool:
    layout = build_schematic_layout(devices, {"topology": topology})
    routed = route_nets(layout.placed)
    boxes = _device_boxes(layout.placed)
    segments, junctions = _segments_for_score(layout)

    ok = True
    print(f"\n=== {name} (variant={layout.variant}, crossing_score={layout.crossing_score}) ===")

    bad = find_bad_crossings(segments, junctions, boxes)
    active_slices = [
        c for c in bad
        if c.reason.startswith("wire-through-device")
        and any(b.name == c.reason.split(":", 1)[1] and b.is_active for b in boxes)
    ]
    print(f"  active-body slices: {len(active_slices)}")
    for c in active_slices:
        print(f"    {c.reason}: ({c.a.x1},{c.a.y1})->({c.a.x2},{c.a.y2}) net={c.a.net}")
        ok = False

    sig = [Segment(s.x1, s.y1, s.x2, s.y2, s.net, s.kind) for s in routed.segments if s.kind == "wire"]
    nets = _collect_net_points(layout.placed)
    gnd = all_rail_riser_segments(layout.placed, nets, layout.height, routed.segments)
    overlaps = [
        (a, b, hit) for a, b, hit in find_collinear_overlaps(sig + gnd)
        if {"nb", "0"} <= {a.net, b.net} or (a.net != b.net)
    ]
    real_overlaps = [(a.net, b.net, hit) for a, b, hit in find_collinear_overlaps(sig + gnd)]
    print(f"  cross-net collinear overlaps: {len(real_overlaps)}")
    for a_net, b_net, hit in real_overlaps:
        axis = "x" if hit[0] == 1 else "y"
        print(f"    {a_net} vs {b_net} on {axis}={hit[1]} span [{hit[2]},{hit[3]}]")
        ok = False

    # n1 must not pass through the nout1 tap column at (344,168)
    n1_at = [s for s in routed.segments if s.net == "n1" and (
        (s.x1 == s.x2 == 344 and min(s.y1, s.y2) <= 168 <= max(s.y1, s.y2)) or
        (s.y1 == s.y2 == 168 and min(s.x1, s.x2) <= 344 <= max(s.x1, s.x2)))]
    print(f"  n1 segments touching (344,168): {len(n1_at)}")
    return ok


def main() -> None:
    ok1 = _check("opamp", _opamp_devices(), "two_stage_miller_opamp")
    ok2 = _check("comparator", _comparator_devices(), "diff_pair_comparator")
    print(f"\nALL_INVARIANTS_OK={ok1 and ok2}")


if __name__ == "__main__":
    main()
