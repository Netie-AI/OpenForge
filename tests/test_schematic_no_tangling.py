"""Tangling regression checks for schematic placement/routing."""

from __future__ import annotations

from openanalog.eda.netlist_graph import SpiceDevice
from openanalog.eda.schematic_geometry import DeviceBox, Segment, find_bad_crossings, score_layout
from openanalog.eda.schematic_layout import (
    SchematicLayout,
    _DIFF_PAIR_LAYOUT,
    _placement_objective,
    _STAGE2_VARIANTS,
    _place_devices,
    _score_layout,
    build_schematic_layout,
)
from openanalog.eda.symbols import terminal_positions


def test_perpendicular_crossing_is_flagged() -> None:
    h = Segment(0, 10, 20, 10, net="a")
    v = Segment(10, 0, 10, 20, net="b")
    bad = find_bad_crossings([h, v], junctions=set())
    assert len(bad) == 1
    assert bad[0].reason == "net-net crossing"


def test_junction_dot_excuses_crossing() -> None:
    h = Segment(0, 10, 20, 10, net="a")
    v = Segment(10, 0, 10, 20, net="b")
    bad = find_bad_crossings([h, v], junctions={(10, 10)})
    assert not bad


def test_wire_through_device_weighted_higher() -> None:
    box = DeviceBox(
        name="M7",
        x=460,
        y=200,
        w=36,
        h=48,
        terminal_nets=frozenset({"vout", "nb", "0"}),
    )
    foreign = Segment(400, 220, 500, 220, net="cc")
    plain_h = Segment(0, 10, 20, 10, net="a")
    plain_v = Segment(10, 0, 10, 20, net="b")
    assert score_layout([foreign], set(), [box]) == 3
    assert score_layout([plain_h, plain_v], set(), [box]) == 1


def test_same_net_slice_through_active_body_is_flagged() -> None:
    """A wire on a device's own net that cuts transversely across an active
    transistor body is a routing defect (the M4 gate-jog regression).

    Connectivity passes because the net is correct, so only the geometry scorer
    can catch it. Pin-escape stubs and passive-body taps must NOT be flagged."""
    # M4-style PMOS load: body x[340,376] y[120,168]; gate net "n1".
    active = DeviceBox(
        name="M4", x=340, y=120, w=36, h=48,
        terminal_nets=frozenset({"n1", "nout1", "vdd"}), kind="M",
    )
    slice_seg = Segment(332, 156, 380, 156, net="n1")  # full-span body cut
    assert score_layout([slice_seg], set(), [active]) == 3

    # Same geometry through a passive (Miller cap) the net taps onto: allowed.
    passive = DeviceBox(
        name="Cc", x=340, y=120, w=36, h=48,
        terminal_nets=frozenset({"n1", "nout1"}), kind="C",
    )
    assert score_layout([slice_seg], set(), [passive]) == 0

    # A pin-escape stub that only touches the body edge is not a slice.
    gate_stub = Segment(370, 144, 380, 144, net="n1")
    assert score_layout([gate_stub], set(), [active]) == 0


def test_opamp_render_path_has_no_active_body_slice() -> None:
    """End-to-end: the production op-amp render path must not route any wire
    transversely through a transistor body (regression guard for the n1->M4 jog)."""
    from openanalog.eda.schematic_geometry import find_bad_crossings
    from openanalog.eda.schematic_layout import _device_boxes, _segments_for_score

    layout = build_schematic_layout(_opamp_devices(), {"topology": "two_stage_miller_opamp"})
    segments, junctions = _segments_for_score(layout)
    boxes = _device_boxes(layout.placed)
    bad = find_bad_crossings(segments, junctions, boxes)
    active_slices = [
        c for c in bad
        if c.reason.startswith("wire-through-device")
        and any(b.name == c.reason.split(":", 1)[1] and b.is_active for b in boxes)
    ]
    assert not active_slices, f"wire slices through transistor body: {active_slices}"


def _opamp_devices() -> list[SpiceDevice]:
    # Mirrors the op-amp core topology nodes (M1..M8 + Iref + Cc).
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


def _nb_x_span(placed) -> int:
    points = []
    for pd in placed:
        for node, pt in terminal_positions(pd.dev, pd.origin, mirror=pd.mirror).items():
            if node.lower() == "nb":
                points.append(pt)
    xs = [pt.x for pt in points]
    return max(xs) - min(xs) if xs else 0


def test_opamp_variant_search_has_score_and_variant() -> None:
    layout = build_schematic_layout(_opamp_devices(), {"topology": "two_stage_miller_opamp"})
    assert layout.variant in _STAGE2_VARIANTS
    assert layout.crossing_score >= 0
    # Keep a conservative cap for geometric tangling, while render-path gates
    # in test_netlist_schematic / connectivity catch floating taps and diagonals.
    assert layout.crossing_score <= 6, (
        f"crossing_score={layout.crossing_score}, tangling regression above tuned envelope"
    )


def test_chosen_variant_not_worse_than_isolated_baseline() -> None:
    devices = _opamp_devices()
    chosen = build_schematic_layout(devices, {"topology": "two_stage_miller_opamp"})

    isolated_map = {k.upper(): v for k, v in _DIFF_PAIR_LAYOUT.items()}
    isolated_map.update({k.upper(): v for k, v in _STAGE2_VARIANTS["isolated"].items()})
    isolated_placed = _place_devices(devices, isolated_map, floorplan_defined=True)
    isolated_layout = SchematicLayout(
        width=0,
        height=0,
        placed=isolated_placed,
        floorplan_defined=True,
        topology="two_stage_miller_opamp",
        variant="isolated",
    )
    isolated_obj = _placement_objective(isolated_layout)
    chosen_obj = _placement_objective(chosen)

    assert chosen_obj <= isolated_obj
    assert _nb_x_span(chosen.placed) <= _nb_x_span(isolated_placed)

