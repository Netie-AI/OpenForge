"""Automated schematic connectivity verification (Phase 0.7 / LVS precursor)."""

from __future__ import annotations

import pytest

from openanalog.forge.spec_envelopes import DEV_MODE_SPECS
from openanalog.eda.netlist_graph import parse_spice_devices
from openanalog.eda.schematic_connectivity import (
    anchor_wire_diffs,
    collinear_net_overlap_errors,
    false_junction_dot_errors,
    hop_centers,
    parse_wire_segments,
    required_hop_centers,
    required_junction_points,
    terminal_map,
    verify_schematic_connectivity,
    verify_terminal_stubs,
    junction_points,
)
from openanalog.eda.schematic_router import route_nets
from openanalog.eda.schematic_layout import build_schematic_layout, render_schematic_svg
from openanalog.eda.symbols import terminal_positions
from openanalog.interface.designer import design

_FLOORPLANS = (
    ("two_stage_miller_opamp", dict(text="RS722 high precision low offset op-amp", budget=40, use_llm=False)),
    (
        "diff_pair_comparator",
        dict(category="comparator", inline_spec="tp<1us vos<5mV iq<10uA", budget=40, use_llm=False),
    ),
)

_ALL_ATTACHMENT_CASES = (
    ("opamp", dict(text="RS722 high precision low offset op-amp", budget=40, use_llm=False)),
    ("comparator", dict(category="comparator", inline_spec=DEV_MODE_SPECS["comparator"], budget=40, use_llm=False)),
    ("switch", dict(category="switch", inline_spec=DEV_MODE_SPECS["switch"], budget=40, use_llm=False)),
    ("charge_pump", dict(category="charge_pump", inline_spec=DEV_MODE_SPECS["charge_pump"], budget=40, use_llm=False)),
    ("vref", dict(category="vref", inline_spec="vref=1.2V line_reg<5mV tempco<100ppm iq<200uA", budget=40, use_llm=False)),
)


@pytest.fixture(scope="module", params=[fp[0] for fp in _FLOORPLANS], ids=[fp[0] for fp in _FLOORPLANS])
def floorplan_case(request):
    name = request.param
    kwargs = next(kw for n, kw in _FLOORPLANS if n == name)
    result = design(**kwargs)
    devices = parse_spice_devices(result["netlist"])
    assert result.get("topology") == name or name in str(result.get("topology", ""))
    return name, result, devices


def test_terminal_to_wire_match(floorplan_case):
    name, result, devices = floorplan_case
    diffs = anchor_wire_diffs(devices, result)
    assert not diffs, f"{name} terminal/wire mismatches:\n" + "\n".join(diffs)


@pytest.mark.parametrize("name,kwargs", _ALL_ATTACHMENT_CASES, ids=[c[0] for c in _ALL_ATTACHMENT_CASES])
def test_all_device_terminals_attached(name: str, kwargs: dict):
    result = design(**kwargs)
    devices = parse_spice_devices(result["netlist"])
    diffs = anchor_wire_diffs(devices, result)
    assert not diffs, f"{name} terminal/wire mismatches:\n" + "\n".join(diffs)


def test_no_connectivity_violations(floorplan_case):
    name, result, devices = floorplan_case
    errors = verify_schematic_connectivity(devices, result)
    assert not errors, f"{name} connectivity errors:\n" + "\n".join(errors)


def test_mirrored_device_anchors_match_svg_transform(floorplan_case):
    """Mirrored drain/source terminals land on routed wires (same transform as render_symbol)."""
    _, result, devices = floorplan_case
    layout = build_schematic_layout(devices, result)
    svg = render_schematic_svg(devices, result)
    segments = parse_wire_segments(svg)
    for pd in layout.placed:
        if not pd.mirror:
            continue
        for node, pt in terminal_positions(pd.dev, pd.origin, mirror=True).items():
            if node == "0" or node.lower().startswith("vin"):
                continue
            on_wire = any(
                (seg[0] == pt.x and seg[1] == pt.y)
                or (seg[2] == pt.x and seg[3] == pt.y)
                or (
                    (seg[0] == seg[2] == pt.x and min(seg[1], seg[3]) <= pt.y <= max(seg[1], seg[3]))
                    or (seg[1] == seg[3] == pt.y and min(seg[0], seg[2]) <= pt.x <= max(seg[0], seg[2]))
                )
                for seg in segments
                if not seg[4]
            )
            assert on_wire, f"{pd.dev.name}.{node} mirrored anchor ({pt.x},{pt.y}) off wire"


def test_io_stubs_reach_terminals(floorplan_case):
    """External IO stubs must land on input/output device terminals."""
    name, result, devices = floorplan_case
    from openanalog.eda.schematic_connectivity import _verify_io_stubs, _io_terminal_targets

    svg = render_schematic_svg(devices, result)
    layout = build_schematic_layout(devices, result)
    segments = parse_wire_segments(svg)
    targets = _io_terminal_targets(layout.placed)
    assert targets, f"{name}: no IO terminals found in layout"
    errors = _verify_io_stubs(layout.placed, segments)
    assert not errors, f"{name} IO stub errors:\n" + "\n".join(errors)


def test_netlist_pins_match_terminal_map(floorplan_case):
    name, result, devices = floorplan_case
    layout = build_schematic_layout(devices, result)
    placed_names = {pd.dev.name.upper() for pd in layout.placed}
    tmap = terminal_map(layout.placed)
    for dev in devices:
        if dev.name.upper() not in placed_names:
            continue
        for node in dev.nodes:
            if node == "0":
                continue
            pts = [
                pt
                for pt, pins in tmap.items()
                if any(
                    pin_name.startswith(f"{dev.name.upper()}.") and pin_node == node.lower()
                    for pin_name, pin_node in pins
                )
            ]
            assert pts, f"{name}: {dev.name}.{node} has no placed terminal"


def test_terminal_stub_collinear(floorplan_case):
    """Phase 0.8: every terminal emits a stub before the first fold."""
    name, result, devices = floorplan_case
    layout = build_schematic_layout(devices, result)
    svg = render_schematic_svg(devices, result)
    errors = verify_terminal_stubs(layout.placed, svg)
    assert not errors, f"{name} terminal stub errors:\n" + "\n".join(errors)


def test_terminal_stub_check_fails_on_legacy_router(floorplan_case):
    """Stub verifier must reject old centroid-star routes (no port stubs)."""
    name, result, devices = floorplan_case
    layout = build_schematic_layout(devices, result)
    svg = render_schematic_svg(devices, result)
    # Legacy SVG has no terminal-stub class lines.
    legacy_svg = svg.replace(" terminal-stub", "")
    errors = verify_terminal_stubs(layout.placed, legacy_svg)
    assert errors, f"{name}: legacy router should fail stub check (got 0 errors)"


@pytest.mark.parametrize("name,kwargs", _ALL_ATTACHMENT_CASES, ids=[c[0] for c in _ALL_ATTACHMENT_CASES])
def test_multiterminal_nets_have_junction_dot(name: str, kwargs: dict):
    """Every 3+ arm electrical node (incl. interior taps) must render a junction dot."""
    result = design(**kwargs)
    devices = parse_spice_devices(result["netlist"])
    svg = render_schematic_svg(devices, result)
    required = required_junction_points(devices, result)
    drawn = junction_points(svg)
    missing = required - drawn
    assert not missing, f"{name} missing junction dots at {sorted(missing)}"


@pytest.mark.parametrize("name,kwargs", _ALL_ATTACHMENT_CASES, ids=[c[0] for c in _ALL_ATTACHMENT_CASES])
def test_unconnected_crossings_have_hop(name: str, kwargs: dict):
    """Unrelated-net crossings must show a wire-hop arc, not a flat line-over-line."""
    result = design(**kwargs)
    devices = parse_spice_devices(result["netlist"])
    svg = render_schematic_svg(devices, result)
    required = required_hop_centers(devices, result)
    drawn = hop_centers(svg)
    missing = required - drawn
    assert not missing, f"{name} missing wire hops at {sorted(missing)}"


@pytest.mark.parametrize("name,kwargs", _ALL_ATTACHMENT_CASES, ids=[c[0] for c in _ALL_ATTACHMENT_CASES])
def test_no_collinear_net_track_overlap(name: str, kwargs: dict):
    """Distinct nets must not share a collinear wire track (false short)."""
    result = design(**kwargs)
    devices = parse_spice_devices(result["netlist"])
    errors = collinear_net_overlap_errors(devices, result)
    assert not errors, f"{name} collinear track overlaps:\n" + "\n".join(errors)


@pytest.mark.parametrize("name,kwargs", _ALL_ATTACHMENT_CASES, ids=[c[0] for c in _ALL_ATTACHMENT_CASES])
def test_junction_dots_not_on_foreign_nets(name: str, kwargs: dict):
    """Junction dots must belong to one net only — no false-short notation."""
    result = design(**kwargs)
    devices = parse_spice_devices(result["netlist"])
    errors = false_junction_dot_errors(devices, result)
    assert not errors, f"{name} false junction dots:\n" + "\n".join(errors)


def test_opamp_n1_does_not_share_nout1_track_at_344_168() -> None:
    """Regression: n1 mirror bus must not collinearly overlap nout1 at (344,168)."""
    from openanalog.eda.schematic_router import _is_segment_endpoint, _is_segment_interior

    result = design(text="RS722 high precision low offset op-amp", budget=40, use_llm=False)
    devices = parse_spice_devices(result["netlist"])
    layout = build_schematic_layout(devices, result)
    routed = route_nets(layout.placed)
    n1 = [s for s in routed.segments if s.net == "n1"]
    assert not any(
        _is_segment_interior(344, 168, s)
        or _is_segment_endpoint(344, 168, s)
        for s in n1
    ), "n1 must not pass through nout1 tap column at y=168"
    overlaps = collinear_net_overlap_errors(devices, result)
    assert not any("n1" in e and "nout1" in e for e in overlaps), overlaps


def test_opamp_m8_source_gnd_does_not_overlap_nb_bias_trunk() -> None:
    """Regression: M8 source-GND riser must never collinearly overlap the nb bias
    trunk. Originally both fought over column x=192; the per-net routing margin
    lets nb relocate, so the invariant is now the general one (no shared track),
    not the stale x=192 proxy."""
    from openanalog.eda.schematic_layout import all_rail_riser_segments, _collect_net_points
    from openanalog.eda.schematic_geometry import Segment, find_collinear_overlaps

    result = design(text="RS722 high precision low offset op-amp", budget=40, use_llm=False)
    devices = parse_spice_devices(result["netlist"])
    overlaps = collinear_net_overlap_errors(devices, result)
    assert not any("nb" in e and "0" in e for e in overlaps), overlaps
    layout = build_schematic_layout(devices, result)
    routed = route_nets(layout.placed)
    nets = _collect_net_points(layout.placed)
    gnd = all_rail_riser_segments(layout.placed, nets, layout.height, routed.segments)
    signal = [
        Segment(s.x1, s.y1, s.x2, s.y2, s.net, s.kind)
        for s in routed.segments
        if s.kind == "wire"
    ]
    nb_gnd_overlap = [
        (a.net, b.net, hit)
        for a, b, hit in find_collinear_overlaps(signal + gnd)
        if {"nb", "0"} <= {a.net, b.net}
    ]
    assert not nb_gnd_overlap, nb_gnd_overlap


def test_opamp_n1_m4_gate_riser_routes_around_m4_body() -> None:
    """Regression (the flagged defect): the n1 mirror tie must reach M4's gate via a
    riser on M4's outer (right) side and route AROUND the transistor body — it must
    not jog to mid-body (the old y=156 cut straight across M4's channel)."""
    from openanalog.eda.schematic_geometry import find_bad_crossings
    from openanalog.eda.schematic_layout import _device_boxes, _segments_for_score

    result = design(text="RS722 high precision low offset op-amp", budget=40, use_llm=False)
    devices = parse_spice_devices(result["netlist"])
    layout = build_schematic_layout(devices, result)
    routed = route_nets(layout.placed)
    n1_vert = [s for s in routed.segments if s.net == "n1" and s.x1 == s.x2 == 380]
    assert len(n1_vert) == 1, n1_vert
    seg = n1_vert[0]
    assert min(seg.y1, seg.y2) == 144, f"riser must reach M4 gate at y=144: {seg}"
    # Must descend past M4's body bottom (y=168) — i.e. route around the body,
    # not terminate mid-body at the old y=156 slice jog.
    assert max(seg.y1, seg.y2) >= 168, f"riser must route around M4 body, got {seg}"

    segments, junctions = _segments_for_score(layout)
    boxes = _device_boxes(layout.placed)
    m4_slices = [
        c for c in find_bad_crossings(segments, junctions, boxes)
        if c.reason == "wire-through-device:M4"
    ]
    assert not m4_slices, f"n1 must not slice through M4 body: {m4_slices}"
