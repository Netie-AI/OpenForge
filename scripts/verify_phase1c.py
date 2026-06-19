#!/usr/bin/env python3
"""Phase 1c verification: charge pump vs RS2660 bar."""
from __future__ import annotations

from collections import Counter

from openanalog.forge.sizer import _passes
from openanalog.forge.spec_envelopes import DEV_MODE_SPECS
from openanalog.forge.topologies.charge_pump import ChargePumpParams, ChargePumpTopology
from openanalog.interface.designer import design

RS2660 = DEV_MODE_SPECS["charge_pump"]
BUDGET = 250
SEEDS = [1, 3, 7, 11, 19, 42]


def _ratio(a: float, b: float) -> str:
    return f"{a / b:.2f}x" if b else "inf"


def _dup_device_names(netlist: str) -> list[str]:
    names = []
    for line in netlist.splitlines():
        s = line.strip()
        if not s or s.startswith("*") or s.startswith("."):
            continue
        if s[0] in "MRCVDI":
            names.append(s.split()[0])
    return [n for n, c in Counter(names).items() if c > 1]


def main() -> None:
    topo = ChargePumpTopology()
    default = topo.default_params()
    dm = topo.measure(default, with_full=True)

    print("=" * 70)
    print("1. DEFAULT vs SEED=19 SIZED")
    print("=" * 70)
    r19 = design(inline_spec=RS2660, budget=BUDGET, seed=19, record_kg=False)
    sized_p = r19["params"]

    print("\n(a) DEFAULT:")
    print(f"    {default.as_dict()}")
    print(f"    vout={dm.values.get('vout_V')} V ripple={dm.values.get('ripple_mV')} mV settle={dm.values.get('settle_ms')} ms")

    print("\n(b) SEED=19 sized:")
    print(f"    {sized_p}")
    m = r19["metrics"]
    print(f"    vout={m.get('vout_V')} V ripple={m.get('ripple_mV')} mV settle={m.get('settle_ms')} ms")
    print(f"    meets_all={r19['meets_all']}")

    print("\n(c) Parameter deltas (sized / default):")
    for k in default.as_dict():
        dv, sv = default.as_dict()[k], sized_p[k]
        print(f"    {k:12s}: {dv:.6g} -> {sv:.6g}  ({_ratio(sv, dv) if isinstance(dv, (int, float)) and dv else 'n/a'})")

    print("\n(d) Causal story:")
    print(
        "    Bootstrap fix (8297008/2c90319) closed vout — sizing was confirmatory only "
        f"(default {dm.values.get('vout_V'):.3f}V -> sized {m.get('vout_V'):.3f}V)."
    )

    print("\n(e) Target-mode tolerance (_passes default tol=0.05 = 5%):")
    vout = float(m.get("vout_V", 0))
    target = 5.0
    tol = 0.05
    print(f"    vout={vout:.3f} target={target} pass band [{target * (1 - tol):.3f},{target * (1 + tol):.3f}]")
    print(f"    _passes at 5%: {_passes(vout, target, 'target', tol=tol)}")
    print(f"    would pass old 30% band [3.5,6.5]: {abs(vout - target) <= target * 0.30}")

    dups = _dup_device_names(r19["netlist"])
    print(f"\n(f) Duplicate device names (seed=19 netlist): {dups if dups else 'NONE'}")

    print("\n" + "=" * 70)
    print("2. SEED SENSITIVITY (budget=250)")
    print("=" * 70)
    pass_n = 0
    for seed in SEEDS:
        r = design(inline_spec=RS2660, budget=BUDGET, seed=seed, record_kg=False)
        ok = r["meets_all"]
        pass_n += int(ok)
        met = r["metrics"]
        print(
            f"  seed={seed:2d} meets_all={ok} vout={met.get('vout_V'):.4f} "
            f"ripple={met.get('ripple_mV'):.3f} settle={met.get('settle_ms'):.4f} ms"
        )
    print(f"\n  Pass rate: {pass_n}/{len(SEEDS)}")

    print("\n" + "=" * 70)
    print("3. PRIOR ~4.1-4.3V failures — topology fix, not target slack")
    print("=" * 70)
    # Pre-bootstrap era params (designs.jsonl ~4.27V with stages=1 or old diode pump)
    hist = ChargePumpParams(stages=1, cap_F=100e-9, freq_Hz=50e3, rload_ohm=50e3)
    hm = topo.measure(hist, with_full=True)
    print(f"  stages=1 legacy-style params today (min 2 enforced): vout={hm.values.get('vout_V')} V")
    hist2 = ChargePumpParams(stages=2, cap_F=100e-9, freq_Hz=500e3, rload_ohm=100e3, w_switch=80)
    hm2 = topo.measure(hist2, with_full=True)
    print(f"  2-stage bootstrapped defaults: vout={hm2.values.get('vout_V')} V")
    print("  Historical ~4.27V records = pre-8297008 diode/NMOS-without-bootstrap topology.")
    print("  Bootstrapped NMOS + gate drive above VDD fixed in commits 2c90319 / 8297008.")

    print("\n" + "=" * 70)
    print("4. BENCH SANITY — RS2660-style assumptions")
    print("=" * 70)
    print("  VDD=5V, bootstrapped 2-stage Dickson, avg vout over last 30% of tran window.")
    print("  Product sample: vout=5.0V, ripple=30mV, settle=3ms.")
    print(f"  Sized seed=19: vout={m.get('vout_V'):.3f}V ripple={m.get('ripple_mV'):.3f}mV settle={m.get('settle_ms'):.4f}ms")


if __name__ == "__main__":
    main()
