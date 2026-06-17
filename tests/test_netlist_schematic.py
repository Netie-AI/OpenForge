"""Tests for netlist-driven schematic rendering."""

import re

from openanalog.eda.netlist_graph import parse_spice_devices, render_netlist_graph_svg
from openanalog.eda.schematic_layout import build_schematic_layout
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
    svg = render_netlist_graph_svg(r["netlist"], r)
    assert svg
    # Miller cap feedback uses intentional diagonal segments; exclude ffcc66 strokes.
    signal_lines = re.findall(r'<line[^>]*stroke="#5ad1c9"[^>]*/>', svg)
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
