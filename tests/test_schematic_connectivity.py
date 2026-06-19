"""Automated schematic connectivity verification (Phase 0.7 / LVS precursor)."""

from __future__ import annotations

import pytest

from openanalog.eda.netlist_graph import parse_spice_devices
from openanalog.eda.schematic_connectivity import (
    anchor_wire_diffs,
    parse_wire_segments,
    terminal_map,
    verify_schematic_connectivity,
)
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
                if (dev.name.upper(), node.lower()) in pins
            ]
            assert pts, f"{name}: {dev.name}.{node} has no placed terminal"
