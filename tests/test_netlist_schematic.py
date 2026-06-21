"""Tests for netlist-driven schematic rendering."""

import re

from openanalog.eda.netlist_graph import parse_spice_devices, render_netlist_graph_svg
from openanalog.eda.schematic_connectivity import parse_terminal_stub_segments, parse_wire_segments
from openanalog.eda.schematic_layout import build_schematic_layout
from openanalog.eda.schematic_router import terminal_stub
from openanalog.eda.schematic import render_svg
from openanalog.interface.designer import design

_LINE_RE = re.compile(r'<line x1="(\d+)" y1="(\d+)" x2="(\d+)" y2="(\d+)"')


def _diagonal_lines(svg: str) -> list[tuple[int, int, int, int]]:
    diags = []
    for m in _LINE_RE.finditer(svg):
        x1, y1, x2, y2 = (int(m.group(i)) for i in range(1, 5))
        if x1 != x2 and y1 != y2:
            diags.append((x1, y1, x2, y2))
    return diags


def _point_on_segment(x: int, y: int, x1: int, y1: int, x2: int, y2: int) -> bool:
    if x1 == x2 == x:
        return min(y1, y2) <= y <= max(y1, y2)
    if y1 == y2 == y:
        return min(x1, x2) <= x <= max(x1, x2)
    return False


def _is_stub_segment(seg: tuple[int, int, int, int, bool], stubs: set[tuple[int, int, int, int]]) -> bool:
    x1, y1, x2, y2, _ = seg
    return (x1, y1, x2, y2) in stubs or (x2, y2, x1, y1) in stubs


def _device_y_positions(svg: str, names: list[str]) -> dict[str, int]:
    """Approximate row from symbol label text y coordinate."""
    ys: dict[str, int] = {}
    for name in names:
        m = re.search(rf'<text[^>]*>{name}</text>', svg)
        if m:
            start = svg.rfind("<text", 0, m.start())
            ym = re.search(r'y="(\d+)"', svg[start:m.start()])
            if ym:
                ys[name] = int(ym.group(1))
    return ys


def test_parse_opamp_devices():
    r = design(text="RS722 high precision low offset op-amp", budget=40, use_llm=False)
    devs = parse_spice_devices(r["netlist"])
    names = {d.name for d in devs}
    assert "M1" in names
    assert "M6" in names
    assert any(d.kind == "M" for d in devs)


def test_render_netlist_graph_has_multiple_devices():
    r = design(text="RS722 high precision low offset op-amp", budget=40, use_llm=False)
    svg = render_netlist_graph_svg(r["netlist"], r)
    assert svg
    assert "M1" in svg
    assert "M6" in svg
    assert "<line" in svg


def test_render_svg_uses_schematic_for_opamp():
    r = design(text="RS722 high precision low offset op-amp", budget=40, use_llm=False)
    svg = render_svg(r)
    assert "schematic" in svg
    assert "device graph" not in svg
    assert "M1" in svg
    assert "<rect" not in svg or "viewBox" in svg  # no device boxes


def test_render_svg_uses_schematic_for_comparator():
    r = design(category="comparator", inline_spec="tp<1us vos<5mV iq<10uA", budget=40, use_llm=False)
    svg = render_svg(r)
    assert "schematic" in svg
    assert "M1" in svg or "M2" in svg


def test_wires_are_orthogonal():
    r = design(text="RS722 high precision low offset op-amp", budget=40, use_llm=False)
    svg = render_svg(r)
    assert svg
    signal_lines = re.findall(r'<line[^>]*class="[^"]*signal-wire[^"]*"[^>]*/>', svg)
    assert signal_lines, "expected signal-wire segments in schematic SVG"
    for tag in signal_lines:
        m = _LINE_RE.search(tag)
        assert m, tag
        x1, y1, x2, y2 = (int(m.group(i)) for i in range(1, 5))
        assert x1 == x2 or y1 == y2, f"diagonal wire: {tag}"


def test_mosfet_symbols_not_boxes():
    r = design(text="RS722 high precision low offset op-amp", budget=40, use_llm=False)
    svg = render_netlist_graph_svg(r["netlist"], r)
    assert svg
    assert "<polygon" in svg  # bulk arrow
    assert 'stroke="#7aa2ff"' in svg  # MOSFET channel/gate strokes


def test_vdd_gnd_rails():
    r = design(text="RS722 high precision low offset op-amp", budget=40, use_llm=False)
    svg = render_netlist_graph_svg(r["netlist"], r)
    assert svg
    assert ">VDD</text>" in svg
    assert ">GND</text>" in svg
    rails = [m for m in _LINE_RE.finditer(svg) if abs(int(m.group(2)) - int(m.group(4))) <= 2]
    assert len(rails) >= 2


def test_miller_cap_terminal_stubs_attach_to_signal_backbone():
    r = design(text="RS722 high precision low offset op-amp", budget=40, use_llm=False)
    svg = render_svg(r)
    devs = parse_spice_devices(r["netlist"])
    layout = build_schematic_layout(devs, r)

    wire_segments = parse_wire_segments(svg)
    stub_segments = set(parse_terminal_stub_segments(svg))
    backbone = [
        seg
        for seg in wire_segments
        if not seg[4] and not _is_stub_segment(seg, stub_segments)
    ]
    assert backbone, "expected routed signal backbone segments"

    cc = next((pd for pd in layout.placed if pd.dev.name.upper() == "CC"), None)
    assert cc is not None, "expected Miller cap Cc in opamp layout"
    for node in cc.dev.nodes:
        stub = terminal_stub(cc.dev, cc.origin, node, mirror=cc.mirror)
        sx, sy = stub.stub_end.x, stub.stub_end.y
        attached = any(
            _point_on_segment(sx, sy, x1, y1, x2, y2) for x1, y1, x2, y2, _ in backbone
        )
        assert attached, f"Cc.{node} stub_end ({sx},{sy}) not tapped to signal backbone"


def test_opamp_input_polarity_labels_match_topology():
    r = design(text="RS722 high precision low offset op-amp", budget=40, use_llm=False)
    svg = render_svg(r)
    assert '>IN-</text>' in svg
    assert '>IN+</text>' in svg
    # In this topology vinp (M1 gate) is inverting and is drawn on the left edge.
    assert re.search(r'<text x="50" y="\d+"[^>]*>IN-</text>', svg), "left input must be IN- for opamp"


def test_no_duplicate_terminal_stub_segments():
    r = design(text="RS722 high precision low offset op-amp", budget=40, use_llm=False)
    svg = render_svg(r)
    stubs = parse_terminal_stub_segments(svg)
    norm = {(x1, y1, x2, y2) if (x1, y1, x2, y2) <= (x2, y2, x1, y1) else (x2, y2, x1, y1) for x1, y1, x2, y2 in stubs}
    assert len(stubs) == len(norm), "terminal stubs should not contain duplicate segments"


def test_terminal_stubs_use_fixed_escape_length():
    r = design(text="RS722 high precision low offset op-amp", budget=40, use_llm=False)
    svg = render_svg(r)
    stubs = parse_terminal_stub_segments(svg)
    assert stubs, "expected terminal stubs in schematic SVG"
    lengths = {abs(x2 - x1) + abs(y2 - y1) for x1, y1, x2, y2 in stubs}
    assert lengths == {10}, f"expected fixed 10px escape stubs, got {sorted(lengths)}"


def test_opamp_floorplan_row_order():
    r = design(text="RS722 high precision low offset op-amp", budget=40, use_llm=False)
    devs = parse_spice_devices(r["netlist"])
    layout = build_schematic_layout(devs, r)
    by_name = {pd.dev.name.upper(): pd.origin.y for pd in layout.placed}
    assert by_name["M8"] > by_name["M5"]  # bias below tail
    assert by_name["M1"] > by_name["M3"]  # input below load
    assert layout.floorplan_defined


def test_comparator_has_defined_floorplan():
    r = design(category="comparator", inline_spec="tp<1us vos<5mV iq<10uA", budget=40, use_llm=False)
    devs = parse_spice_devices(r["netlist"])
    layout = build_schematic_layout(devs, r)
    assert layout.floorplan_defined
    assert layout.topology == "diff_pair_comparator"
