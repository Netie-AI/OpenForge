"""Tests for Masala → ngspice-flat converter (Phase 2b)."""

from openanalog.ingestion.converter import (
    convert_to_ngspice_flat,
    normalize_for_forge,
    prepare_seed_deck,
)
from openanalog.ingestion.dialect import detect_dialect

MASALA_SAMPLE = """M0 (IOUT1 net4 VSS VSS) nmos4
R0 (VDD net4) resistor
R1 (net4 VSS) resistor
"""

MASALA_MOS = "M0 (d g s b) nmos4 W=1u L=0.5u"


def test_convert_mosfet_paren_to_flat():
    result = convert_to_ngspice_flat("M0 (IOUT1 net4 VSS VSS) nmos4")
    assert result.converted
    assert "M0 IOUT1 net4 0 0" in result.netlist
    assert "nmos_ana" in result.netlist
    assert "(" not in result.netlist.split("\n")[0]


def test_convert_resistor_and_supply_normalize():
    result = convert_to_ngspice_flat(MASALA_SAMPLE)
    assert "R0 vdd net4" in result.netlist
    assert "R1 net4 0" in result.netlist
    assert result.converted


def test_convert_subckt_passthrough():
    text = """subckt INVERTER A Q VDD VSS
M0 (Q A VDD VDD) pmos4
M1 (Q A VSS VSS) nmos4
ends INVERTER
I0 (in out VDD VSS) INVERTER
"""
    result = convert_to_ngspice_flat(text)
    assert ".subckt INVERTER" in result.netlist
    assert ".ends" in result.netlist
    assert "X0" in result.netlist or "X_I0" in result.netlist


def test_unknown_line_recorded():
    result = convert_to_ngspice_flat("GARBAGE not a spice line\nM0 (a b 0 0) nmos4")
    assert any("unconverted" in w or "unknown" in w for w in result.warnings)


def test_ngspice_flat_passthrough():
    flat = "V1 in 0 DC 1\nR1 out in 1k\n.end\n"
    result = convert_to_ngspice_flat(flat)
    assert not result.converted
    assert result.netlist == flat


def test_prepare_seed_deck_adds_models_and_supply():
    flat, _, _ = normalize_for_forge(MASALA_SAMPLE)
    deck = prepare_seed_deck(flat)
    assert "nmos_ana" in deck or ".model" in deck
    assert "VDD_SUPPLY vdd 0" in deck
    assert ".end" in deck.lower()


def test_normalize_for_forge_returns_dialect():
    _, warnings, dialect = normalize_for_forge(MASALA_SAMPLE)
    assert dialect == "masala-paren"
    assert detect_dialect(MASALA_MOS) == "masala-paren"
