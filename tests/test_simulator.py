from openanalog.forge.simulator import (
    _parse_ac_results,
    is_analoggenie_syntax,
    is_simulatable,
    simulate,
    simulate_netlist,
)


def test_parse_ac_results():
    raw = "gain_db_max = 62.5\nbw_3db = 2.1e6"
    bw, gain = _parse_ac_results(raw)
    assert gain == 62.5
    assert abs(bw - 2.1) < 0.01


def test_analoggenie_syntax_detected():
    netlist = "M0 (IOUT1 net4 VSS VSS) nmos4\nR0 (VDD net4) resistor"
    assert is_analoggenie_syntax(netlist)
    assert not is_simulatable(netlist)
    r = simulate_netlist(netlist)
    assert not r.sim_ok
    assert r.failed.get("syntax") == "analoggenie_custom_format"


def test_standard_spice_not_analoggenie():
    netlist = "V1 in 0 DC 1\nR1 out in 1k\nC1 out 0 1p\n.end"
    assert not is_analoggenie_syntax(netlist)
    assert is_simulatable(netlist)


def test_simulate_without_ngspice():
    r = simulate("* minimal\nV1 in 0 DC 1\n.end\n")
    assert r.ok is False or r.error or r.raw
