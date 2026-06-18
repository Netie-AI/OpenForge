"""Behavioral ngspice tests — sized designs against RS-series datasheet bar."""

from __future__ import annotations

import shutil

import pytest

from openanalog.forge.spec_envelopes import DATASHEET_PARTS, DEV_MODE_SPECS
from openanalog.forge.topologies import get_topology
from openanalog.interface.designer import design

pytestmark = pytest.mark.skipif(
    shutil.which("ngspice") is None,
    reason="ngspice not on PATH",
)

# DEV_MODE_SPECS values are the RS-series datasheet envelopes (see spec_envelopes.py).
RS8901_SPEC = DEV_MODE_SPECS["comparator"]
RS2105_SPEC = DEV_MODE_SPECS["switch"]
RS2660_SPEC = DEV_MODE_SPECS["charge_pump"]

SIZE_BUDGET = {"comparator": 250, "opamp": 200, "switch": 250, "charge_pump": 250}
SIZE_SEED = {"comparator": 7, "opamp": 42, "switch": 11, "charge_pump": 19}


def _design(cat: str) -> dict:
    return design(
        inline_spec=DEV_MODE_SPECS[cat],
        budget=SIZE_BUDGET.get(cat, 200),
        seed=SIZE_SEED.get(cat, 42),
        record_kg=False,
    )


def test_comparator_meets_rs8901_bar():
    """Phase 1a gate: real ngspice sizing must hit RS8901 tp/vos/iq on diff_pair_comparator."""
    assert DATASHEET_PARTS["comparator"] == "RS8901"
    result = design(
        inline_spec=RS8901_SPEC,
        budget=SIZE_BUDGET["comparator"],
        seed=SIZE_SEED["comparator"],
        record_kg=False,
    )
    assert result["topology"] == "diff_pair_comparator"
    metrics = result["metrics"]
    assert metrics.get("tp_us") is not None, "tp must come from ngspice .tran (not scoring stub)"
    assert metrics.get("iq_uA") is not None, "iq must come from ngspice OP (not scoring stub)"
    assert metrics["tp_us"] < 1.0
    assert metrics["iq_uA"] < 1.0
    assert metrics["vos_mV"] < 3.0
    assert result["meets_all"], {
        k: v for k, v in result["compliance"].items() if v.get("pass") is False
    }


def test_opamp_meets_datasheet_bar():
    result = _design("opamp")
    assert result["meets_all"], {
        k: v for k, v in result["compliance"].items() if v.get("pass") is False
    }


def test_switch_meets_rs2105_bar():
    """Phase 1b gate: real ngspice sizing must hit RS2105 ron/bw/ton/toff on cmos_transmission_gate."""
    assert DATASHEET_PARTS["switch"] == "RS2105"
    result = design(
        inline_spec=RS2105_SPEC,
        budget=SIZE_BUDGET["switch"],
        seed=SIZE_SEED["switch"],
        record_kg=False,
    )
    assert result["topology"] == "cmos_transmission_gate"
    metrics = result["metrics"]
    assert metrics.get("ron_ohm") is not None, "ron must come from ngspice OP (not scoring stub)"
    assert metrics.get("ton_ns") is not None, "ton must come from ngspice .tran"
    assert metrics.get("toff_ns") is not None, "toff must come from ngspice .tran"
    assert metrics["ron_ohm"] < 50.0
    assert metrics["bw_MHz"] > 10.0
    assert metrics["ton_ns"] < 20.0
    assert metrics["toff_ns"] < 20.0
    assert result["meets_all"], {
        k: v for k, v in result["compliance"].items() if v.get("pass") is False
    }


def test_charge_pump_meets_rs2660_bar():
    """Phase 1c gate: real ngspice sizing must hit RS2660 vout/ripple/settle on dickson_charge_pump."""
    assert DATASHEET_PARTS["charge_pump"] == "RS2660"
    result = design(
        inline_spec=RS2660_SPEC,
        budget=SIZE_BUDGET["charge_pump"],
        seed=SIZE_SEED["charge_pump"],
        record_kg=False,
    )
    assert result["topology"] == "dickson_charge_pump"
    metrics = result["metrics"]
    assert metrics.get("vout_V") is not None, "vout must come from ngspice .tran avg"
    assert metrics.get("ripple_mV") is not None, "ripple must come from ngspice .tran pp"
    assert metrics.get("settle_ms") is not None, "settle must come from ngspice .tran"
    assert metrics["vout_V"] >= 4.75  # 5% target-mode floor (same as score_design)
    assert metrics["ripple_mV"] < 50.0
    assert metrics["settle_ms"] < 5.0
    assert result["meets_all"], {
        k: v for k, v in result["compliance"].items() if v.get("pass") is False
    }


def test_vref_deferred_to_phase3():
    from openanalog.sim.models import set_active_model_set

    set_active_model_set("bundled")
    t = get_topology("vref")
    m = t.measure(t.default_params(), with_full=True)
    assert not m.ok
    assert any("Phase 3" in w or "deferred" in w.lower() for w in m.warnings)
