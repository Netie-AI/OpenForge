"""Per-category topology scoring tests (no ngspice)."""

from openanalog.forge.sizer import score_design
from openanalog.forge.topologies.base import TopologyMetrics
from openanalog.forge.topologies import (
    ComparatorTopology,
    AnalogSwitchTopology,
    ChargePumpTopology,
    VRefTopology,
)


def test_comparator_score():
    topo = ComparatorTopology()
    m = TopologyMetrics(ok=True, values={"tp_us": 0.5, "vos_mV": 2.0, "iq_uA": 0.8})
    targets = {
        "tp_us": {"value": 1.0, "mode": "max"},
        "vos_mV": {"value": 3.0, "mode": "max"},
        "iq_uA": {"value": 1.0, "mode": "max"},
    }
    c = score_design(m, targets, measurable=topo.measurable_specs(), weights=topo.spec_weights)
    assert c.meets_all is True


def test_switch_score_ron_fail():
    topo = AnalogSwitchTopology()
    m = TopologyMetrics(ok=True, values={"ron_ohm": 100.0, "bw_MHz": 15.0})
    targets = {"ron_ohm": {"value": 50.0, "mode": "max"}, "bw_MHz": {"value": 10.0, "mode": "min"}}
    c = score_design(m, targets, measurable=topo.measurable_specs(), weights=topo.spec_weights)
    assert c.per_spec["ron_ohm"]["pass"] is False


def test_charge_pump_score():
    topo = ChargePumpTopology()
    m = TopologyMetrics(ok=True, values={"vout_V": 5.0, "ripple_mV": 30.0, "settle_ms": 3.0})
    targets = {
        "vout_V": {"value": 5.0, "mode": "target"},
        "ripple_mV": {"value": 50.0, "mode": "max"},
        "settle_ms": {"value": 5.0, "mode": "max"},
    }
    c = score_design(m, targets, measurable=topo.measurable_specs(), weights=topo.spec_weights)
    assert c.meets_all is True


def test_vref_score():
    topo = VRefTopology()
    m = TopologyMetrics(ok=True, values={"vref_V": 1.22, "line_reg_mV": 2.0, "iq_uA": 50.0})
    targets = {
        "vref_V": {"value": 1.2, "mode": "target"},
        "line_reg_mV": {"value": 5.0, "mode": "max"},
        "iq_uA": {"value": 100.0, "mode": "max"},
    }
    c = score_design(m, targets, measurable=topo.measurable_specs(), weights=topo.spec_weights)
    assert c.meets_all is True
