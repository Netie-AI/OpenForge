#!/usr/bin/env python3
"""Quick probes for Phase 1 sizer push."""
from __future__ import annotations

from openanalog.forge.spec_envelopes import DEV_MODE_SPECS
from openanalog.forge.sizer import size
from openanalog.forge.topologies.analog_switch import AnalogSwitchTopology, SwitchParams
from openanalog.forge.topologies.charge_pump import ChargePumpParams, ChargePumpTopology
from openanalog.forge.topologies.comparator import ComparatorParams, ComparatorTopology
from openanalog.interface.datasheet import parse_inline_spec


def probe_comparator() -> None:
    ct = ComparatorTopology()
    print("=== comparator manual Iref sweep ===")
    for iref in [100e-9, 500e-9, 1e-6, 5e-6, 30e-6]:
        p = ComparatorParams(Iref=iref, W1=2, W3=2, W5=2, W6=4, W7=2, Wb=2)
        m = ct.measure(p, with_full=True)
        print(
            f"  Iref={iref*1e9:.0f}nA iq={m.values.get('iq_uA')} "
            f"tp={m.values.get('tp_us')} vos={m.values.get('vos_mV')}"
        )


def probe_switch() -> None:
    st = AnalogSwitchTopology()
    print("=== switch manual W sweep ===")
    for wn, wp, wdrv, ln in [(50, 100, 10, 0.5), (200, 400, 60, 0.3), (500, 1000, 200, 0.3)]:
        p = SwitchParams(Wn=wn, Wp=wp, Wdrv=wdrv, len_n=ln, len_p=ln)
        m = st.measure(p, with_full=True)
        ron = m.values.get("ron_ohm")
        ron_s = f"{ron:.1f}" if ron else "None"
        print(
            f"  Wn={wn} ron={ron_s} "
            f"ton={m.values.get('ton_ns')} toff={m.values.get('toff_ns')} "
            f"bw={m.values.get('bw_MHz')}"
        )


def probe_charge_pump() -> None:
    cp = ChargePumpTopology()
    print("=== charge_pump stages sweep ===")
    for stages in [2, 3, 4]:
        p = ChargePumpParams(stages=stages, rload_ohm=50e3, cap_F=200e-9, freq_Hz=1e6)
        m = cp.measure(p, with_full=True)
        print(f"  stages={stages} vout={m.values.get('vout_V')} ripple={m.values.get('ripple_mV')}")


def run_size(cat: str, budget: int = 200, seed: int = 42) -> None:
    spec = parse_inline_spec(DEV_MODE_SPECS[cat], category=cat)
    print(f"\n=== size {cat} budget={budget} ===")
    cand = size(cat, spec, budget=budget, seed=seed)
    print(f"  meets_all={cand.meets_all} score={cand.score:.4f}")
    print(f"  params={cand.params.as_dict()}")
    print(f"  metrics={cand.metrics.as_dict()}")
    print(f"  fail={ {k: v for k, v in cand.per_spec.items() if v.get('pass') is False} }")


if __name__ == "__main__":
    import sys

    budget = 200
    cats = ["comparator", "switch", "charge_pump", "opamp"]
    args = sys.argv[1:]
    if args and args[0].isdigit():
        budget = int(args.pop(0))
    if args:
        cats = args

    probe_comparator()
    probe_switch()
    probe_charge_pump()
    for cat in cats:
        run_size(cat, budget=budget)
