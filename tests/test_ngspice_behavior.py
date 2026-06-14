"""Behavioral ngspice tests — assert measured values from real simulation runs."""

from __future__ import annotations

import shutil

import pytest

from openanalog.forge.topologies import get_topology

pytestmark = pytest.mark.skipif(
    shutil.which("ngspice") is None,
    reason="ngspice not on PATH",
)


def test_comparator_switches_and_low_vos():
    t = get_topology("comparator")
    m = t.measure(t.default_params(), with_full=True)
    assert m.ok, m.raw
    assert m.values["vos_mV"] is not None and m.values["vos_mV"] < 50
    assert m.values["tp_us"] is not None and m.values["tp_us"] < 20


def test_charge_pump_produces_vout():
    t = get_topology("charge_pump")
    m = t.measure(t.default_params(), with_full=True)
    assert m.ok, m.error or m.raw
    assert m.values["vout_V"] is not None and m.values["vout_V"] > 2.0
    assert m.values["ripple_mV"] is not None


def test_switch_ron_and_bw():
    t = get_topology("switch")
    m = t.measure(t.default_params(), with_full=True)
    assert m.ok, m.raw
    assert m.values["ron_ohm"] is not None and 1 < m.values["ron_ohm"] < 5000
    assert m.values["bw_MHz"] is not None and m.values["bw_MHz"] > 1


def test_opamp_has_gain_and_gbp():
    t = get_topology("opamp")
    m = t.measure(t.default_params(), with_full=True)
    assert m.ok, m.raw
    assert m.values["aol_dB"] is not None and m.values["aol_dB"] > 60
    assert m.values["gbp_MHz"] is not None and m.values["gbp_MHz"] > 0.5
    # Default PM ~15° is intentional (under-compensated seed); sizer targets spec PM.


def test_vref_deferred_to_phase3():
    t = get_topology("vref")
    m = t.measure(t.default_params(), with_full=True)
    assert not m.ok
    assert any("Phase 3" in w for w in m.warnings)
