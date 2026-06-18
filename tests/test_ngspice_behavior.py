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

SIZE_BUDGET = {"comparator": 250, "opamp": 200, "switch": 250, "charge_pump": 120}
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


def test_charge_pump_meets_datasheet_bar():
    result = _design("charge_pump")
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
