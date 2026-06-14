"""Tests for SPICE dialect detection (Phase 2a)."""

from openanalog.ingestion.dialect import detect_dialect, dialect_breakdown

SPICE_FLAT_SAMPLE = """.title KiCad schematic
V1 in 0 DC 1
R1 out in 1k
C1 out 0 1p
.end
"""

MASALA_SAMPLE = """M0 (IOUT1 net4 VSS VSS) nmos4
R0 (VDD net4) resistor
R1 (net4 VSS) resistor
"""

MASALA_SUBCKT_SAMPLE = """subckt INVERTER A Q VDD VSS
    M0 (Q A VDD VDD) pmos4
    M1 (Q A VSS VSS) nmos4
ends INVERTER
M0 (out in 0 0) nmos4
"""


def test_detect_ngspice_flat():
    assert detect_dialect(SPICE_FLAT_SAMPLE) == "ngspice-flat"


def test_detect_masala_paren():
    assert detect_dialect(MASALA_SAMPLE) == "masala-paren"


def test_detect_masala_subckt_body():
    assert detect_dialect(MASALA_SUBCKT_SAMPLE) == "masala-paren"


def test_detect_unknown_empty():
    assert detect_dialect("") == "unknown"
    assert detect_dialect("   ") == "unknown"


def test_dialect_breakdown():
    counts = dialect_breakdown([SPICE_FLAT_SAMPLE, MASALA_SAMPLE, ""])
    assert counts["ngspice-flat"] == 1
    assert counts["masala-paren"] == 1
    assert counts["unknown"] == 1
