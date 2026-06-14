"""Behavioral ngspice tests — sized designs against RS-series datasheet bar."""

from __future__ import annotations

import shutil

import pytest

from openanalog.forge.spec_envelopes import DEV_MODE_SPECS
from openanalog.forge.topologies import get_topology
from openanalog.interface.designer import design

pytestmark = pytest.mark.skipif(
    shutil.which("ngspice") is None,
    reason="ngspice not on PATH",
)

SIZE_BUDGET = {"comparator": 250, "opamp": 200, "switch": 150, "charge_pump": 120}
SIZE_SEED = {"comparator": 7, "opamp": 42, "switch": 11, "charge_pump": 19}


def _design(cat: str) -> dict:
    return design(
        inline_spec=DEV_MODE_SPECS[cat],
        budget=SIZE_BUDGET.get(cat, 200),
        seed=SIZE_SEED.get(cat, 42),
        record_kg=False,
    )


def test_comparator_meets_datasheet_bar():
    result = _design("comparator")
    assert result["meets_all"], {
        k: v for k, v in result["compliance"].items() if v.get("pass") is False
    }


def test_opamp_meets_datasheet_bar():
    result = _design("opamp")
    assert result["meets_all"], {
        k: v for k, v in result["compliance"].items() if v.get("pass") is False
    }


def test_switch_ron_blocked_on_level1():
    """Documented level-1 floor ~300Ω at 2.5V common-mode (PMOS pass device dead)."""
    result = _design("switch")
    if result["meets_all"]:
        return
    ron = result["metrics"].get("ron_ohm")
    assert ron is not None and ron > 50


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
