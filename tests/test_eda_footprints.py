"""KiCad EDA metadata tests."""

from openanalog.eda.footprints import (
    attach_eda_metadata,
    kicad_footprint_name,
    kicad_symbol_name,
    emit_kicad_sym_stub,
)


def test_kicad_names():
    assert "Amplifier" in kicad_symbol_name("opamp", "SOT23-5")
    assert "Comparator" in kicad_symbol_name("comparator", "SOT23-5")
    assert "SOT-23-5" in kicad_footprint_name("SOT23-5")


def test_attach_eda_metadata():
    result = {
        "spec": {"circuit_type": "comparator", "part": "RS8901"},
        "category": "comparator",
        "package": "SOT23-5",
        "topology": "diff_pair_comparator",
        "supply_V": 5.0,
        "meets_all": True,
        "score": 0.9,
        "metrics": {},
        "compliance": {},
        "params": {},
        "devices": [],
        "netlist": "* test",
        "warnings": [],
    }
    out = attach_eda_metadata(result)
    assert "eda" in out
    assert out["eda"]["kicad_symbol"]
    assert out["eda"]["kicad_footprint"]
    assert "kicad_sym_stub" in out
    assert "openforge" in emit_kicad_sym_stub(design_id="OF_test", circuit_type="opamp", symbol_lib_id="X:Y").lower()
