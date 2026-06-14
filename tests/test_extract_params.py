"""Tests for seed parameter extraction."""

from openanalog.ingestion.converter import extract_params


SAMPLE = """
.param W1=8u L1=1u IREF=20u
M1 d g s b nmos_ana W=12u L=0.8u
M2 d2 g2 s2 b nmos_ana W=12u L=0.8u
Ibias vdd nb 20u
"""


def test_extract_params_wl_and_iref():
    hints = extract_params(SAMPLE)
    assert hints.get("W1") == 8e-6 or hints.get("W1") == 8.0  # .param uses u suffix
    assert "Iref" in hints or "IREF" in hints
