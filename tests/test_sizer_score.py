from openanalog.forge.topologies.base import TopologyMetrics
from openanalog.forge.sizer import score_design

TARGETS = {
    "aol_dB": {"value": 90.0, "mode": "min"},
    "gbp_MHz": {"value": 1.1, "mode": "target"},
    "pm_deg": {"value": 60.0, "mode": "min"},
    "iq_uA": {"value": 80.0, "mode": "max"},
    "slew_Vus": {"value": 0.5, "mode": "min"},
    "cmrr_dB": {"value": 80.0, "mode": "min"},  # not measurable -> N/A
}

MEASURABLE = {"aol_dB", "gbp_MHz", "pm_deg", "iq_uA", "slew_Vus"}


def _metrics(**kw) -> TopologyMetrics:
    m = TopologyMetrics(ok=True)
    m.values = {k: v for k, v in kw.items()}
    return m


def test_meets_all_when_specs_satisfied():
    m = _metrics(aol_dB=96, gbp_MHz=1.08, pm_deg=70, iq_uA=55, slew_Vus=1.0)
    c = score_design(m, TARGETS, measurable=MEASURABLE)
    assert c.meets_all is True
    assert c.per_spec["cmrr_dB"]["pass"] is None
    assert c.per_spec["aol_dB"]["pass"] is True


def test_fails_when_unstable():
    m = _metrics(aol_dB=96, gbp_MHz=1.08, pm_deg=10, iq_uA=55, slew_Vus=1.0)
    c = score_design(m, TARGETS, measurable=MEASURABLE)
    assert c.meets_all is False
    assert c.per_spec["pm_deg"]["pass"] is False


def test_iq_over_budget_fails():
    m = _metrics(aol_dB=96, gbp_MHz=1.08, pm_deg=70, iq_uA=200, slew_Vus=1.0)
    c = score_design(m, TARGETS, measurable=MEASURABLE)
    assert c.per_spec["iq_uA"]["pass"] is False
    assert c.meets_all is False
