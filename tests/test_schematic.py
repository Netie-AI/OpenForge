"""Tests for schematic SVG and KiCad sch export."""

from openanalog.eda.kicad_sch import emit_kicad_sch
from openanalog.eda.schematic import render_svg


def _sample_result():
    return {
        "category": "opamp",
        "topology": "two_stage_miller",
        "meets_all": True,
        "score": 0.95,
        "supply_V": 5.0,
        "spec": {"part": "RS321"},
        "params": {"Wn": 10.0},
        "devices": [{"name": "M1", "W_um": 10.0, "L_um": 0.5}],
        "eda": {
            "design_id": "OF_opamp_RS321",
            "kicad_symbol": "Amplifier_Operational:LM358",
            "kicad_footprint": "Package_TO_SOT_SMD:SOT-23-5",
        },
    }


def test_render_svg_contains_svg_tag():
    svg = render_svg(_sample_result())
    assert "<svg" in svg and "</svg>" in svg
    assert "OPAMP" in svg or "Op-Amp" in svg


def test_emit_kicad_sch_valid():
    sch = emit_kicad_sch(_sample_result())
    assert "(kicad_sch" in sch
    assert "OF_opamp_RS321" in sch
    assert "Amplifier_Operational:LM358" in sch
