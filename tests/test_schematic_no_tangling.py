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

