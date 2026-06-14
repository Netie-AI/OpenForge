"""Tests for forge topology inference."""

from openanalog.forge.topology_detector import infer_topology, resolve_forge_topology

OPAMP_LIKE = """
M1 n1 vinp tail 0 nmos_ana W=10u L=1u
M2 n2 vinn tail 0 nmos_ana W=10u L=1u
M3 n1 n1 vdd vdd pmos_ana W=10u L=1u
M4 vout n1 vdd vdd pmos_ana W=10u L=1u
Cc vout n1 1p
"""

COMPARATOR_LIKE = """
M1 n1 vinp tail 0 nmos_ana W=10u L=1u
M2 n2 vinn tail 0 nmos_ana W=10u L=1u
M6 vout n1 vdd vdd pmos_ana W=10u L=1u
VCLK1 vclk1 0 DC 1.8
"""

SWITCH_LIKE = """
X0 in out ctrl vdd 0 TRANSMISSION_GATE
X1 out load ctrl vdd 0 TRANSMISSION_GATE
"""

CHARGE_PUMP_LIKE = """
D0 vdd clk1 DMOD
D1 clk1 n1 DMOD
C1 vdd n1 100n
C2 n1 n2 100n
VCLK1 clk1 0 pulse(0 1.8 0 1n 1n 1u 2u)
"""


def test_infer_opamp_diff_pair():
    assert infer_topology(OPAMP_LIKE) == "opamp"


def test_infer_comparator_with_clocks():
    assert infer_topology(COMPARATOR_LIKE) == "comparator"


def test_infer_switch_transmission_gate():
    assert infer_topology(SWITCH_LIKE) == "switch"


def test_infer_charge_pump():
    assert infer_topology(CHARGE_PUMP_LIKE) == "charge_pump"


def test_resolve_amplifier_label():
    assert resolve_forge_topology("R1 a b 1k", "amplifier") == "opamp"


def test_unknown_netlist():
    assert infer_topology("R1 a b 1k\nR2 b 0 1k") == "unknown"
