#!/usr/bin/env python3
"""Phase 1a verification pass — evidence before push."""
from __future__ import annotations

import json
import re
from pathlib import Path

from openanalog.forge.spec_envelopes import DEV_MODE_SPECS
from openanalog.forge.topologies.comparator import ComparatorParams, ComparatorTopology
from openanalog.interface.designer import design

RS8901 = DEV_MODE_SPECS["comparator"]
BUDGET = 250
SEEDS = [1, 3, 7, 12]


def _device_graph(netlist: str) -> list[str]:
    """Normalized device lines (topology structure, params as placeholders)."""
    out = []
    for raw in netlist.splitlines():
        line = raw.strip()
        if not line or line.startswith("*"):
            continue
        if line[0] in "MRVI":
            # collapse numeric W/L/R values to keep connectivity-only view
            norm = re.sub(r"\{[^}]+\}", "{}", line)
            norm = re.sub(r"\s+", " ", norm)
            out.append(norm)
    return out


def _fmt_params(d: dict) -> str:
    keys = ["W1", "L1", "W3", "L3", "W5", "L5", "W6", "L6", "W7", "L7", "Wb", "Lb", "Iref", "Rload"]
    parts = []
    for k in keys:
        v = d.get(k)
        if v is None:
            continue
        if k == "Iref":
            parts.append(f"Iref={v*1e9:.1f}nA")
        elif k == "Rload":
            parts.append(f"Rload={v/1e3:.2f}k")
        else:
            parts.append(f"{k}={v:.3f}um" if k.startswith("L") or k.startswith("W") else f"{k}={v}")
    return ", ".join(parts)


def _ratio(a: float, b: float) -> str:
    if b == 0:
        return "inf"
    return f"{a/b:.2f}x"


def main() -> None:
    topo = ComparatorTopology()
    default = topo.default_params()
    default_m = topo.measure(default, with_full=True)

    print("=" * 70)
    print("1. DEFAULT vs SEED=7 SIZED — parameters and netlist structure")
    print("=" * 70)
    r7 = design(inline_spec=RS8901, budget=BUDGET, seed=7, record_kg=False)
    sized_p = r7["params"]

    print("\n(a) DEFAULT params:")
    print(f"    {_fmt_params(default.as_dict())}")
    print(f"    metrics: tp={default_m.values.get('tp_us'):.3f}us iq={default_m.values.get('iq_uA'):.3f}uA vos={default_m.values.get('vos_mV'):.3f}mV")

    print("\n(b) SEED=7 sized params:")
    print(f"    {_fmt_params(sized_p)}")
    print(f"    metrics: tp={r7['metrics']['tp_us']:.3f}us iq={r7['metrics']['iq_uA']:.3f}uA vos={r7['metrics']['vos_mV']:.3f}mV")

    print("\n(c) Parameter deltas (sized / default):")
    for k in default.as_dict():
        dv, sv = default.as_dict()[k], sized_p[k]
        print(f"    {k:5s}: {dv:.6g} -> {sv:.6g}  ({_ratio(sv, dv)})")

    nl_def = topo.emit_netlist(default)
    nl_sized = topo.emit_netlist(ComparatorParams(**{k: sized_p[k] for k in default.as_dict()}))
    g_def, g_sized = _device_graph(nl_def), _device_graph(nl_sized)
    print(f"\n(d) Netlist device count: default={len(g_def)} sized={len(g_sized)}")
    print(f"    Structure identical: {g_def == g_sized}")
    if g_def != g_sized:
        for i, (a, b) in enumerate(zip(g_def, g_sized)):
            if a != b:
                print(f"    diff line {i}: {a} | {b}")

    print("\n(e) Causal story (key moves):")
    print(f"    Iref: {default.Iref*1e9:.0f}nA -> {sized_p['Iref']*1e9:.1f}nA ({_ratio(sized_p['Iref'], default.Iref)} down) -> iq {default_m.values['iq_uA']:.2f} -> {r7['metrics']['iq_uA']:.2f} uA")
    print(f"    W3 (PMOS load): {default.W3:.1f} -> {sized_p['W3']:.1f}um ({_ratio(sized_p['W3'], default.W3)} down) — lighter load on diff node")
    print(f"    W6 (output inv): {default.W6:.1f} -> {sized_p['W6']:.1f}um ({_ratio(sized_p['W6'], default.W6)} down) — smaller output drive")
    print(f"    Rload: {default.Rload/1e3:.0f}k -> {sized_p['Rload']/1e3:.1f}k ({_ratio(sized_p['Rload'], default.Rload)} down) — lighter output load -> faster tp")
    print(f"    W5 (tail cascode): {default.W5:.1f} -> {sized_p['W5']:.1f}um ({_ratio(sized_p['W5'], default.W5)} up)")

    print("\n" + "=" * 70)
    print("2. SEED SENSITIVITY (budget=250)")
    print("=" * 70)
    pass_n = 0
    for seed in SEEDS:
        r = design(inline_spec=RS8901, budget=BUDGET, seed=seed, record_kg=False)
        ok = r["meets_all"]
        pass_n += int(ok)
        m = r["metrics"]
        print(
            f"  seed={seed:2d} meets_all={ok} tp={m.get('tp_us')} iq={m.get('iq_uA')} vos={m.get('vos_mV')}"
        )
    print(f"\n  Pass rate: {pass_n}/{len(SEEDS)}")

    print("\n" + "=" * 70)
    print("3. PRIOR 8us RS8901 ATTEMPTS — reproduce stored params")
    print("=" * 70)
    # From data/designs.jsonl lines 6/10 (identical failed RS8901 run)
    failed_params = {
        "W1": 6.63446,
        "L1": 0.8,
        "W3": 39.65998,
        "L3": 0.8,
        "W5": 4.93233,
        "L5": 0.8,
        "W6": 11.99993,
        "L6": 0.8,
        "W7": 14.73059,
        "L7": 0.8,
        "Wb": 4.0,
        "Lb": 0.8,
        "Iref": 500e-9,
        "Rload": 50e3,
    }
    fp = ComparatorParams(**failed_params)
    fm = topo.measure(fp, with_full=True)
    print(f"  Stored failed params (designs.jsonl): tp=8.12us iq=5.73us (historical)")
    print(f"  Re-measured today same params:        tp={fm.values.get('tp_us')} iq={fm.values.get('iq_uA')} vos={fm.values.get('vos_mV')}")

    # Try to find what seed/budget produces similar params
    for seed in [1, 42, 0]:
        r = design(inline_spec=RS8901, budget=80, seed=seed, record_kg=False)
        print(f"  budget=80 seed={seed}: meets_all={r['meets_all']} tp={r['metrics'].get('tp_us')} iq={r['metrics'].get('iq_uA')}")

    print("\n" + "=" * 70)
    print("3b. OLD vs CURRENT tran deck on same params (root cause of 8us history)")
    print("=" * 70)
    from openanalog.forge.topologies.base import run_ngspice, grab_meas
    from openanalog.sim.models import resolve_models
    from openanalog.forge.blocks.comparator_core import emit as emit_comparator_core

    ms = resolve_models()
    vcm = 2.5
    params_block = f""".param VDD=5.0
.param VCM={vcm}
.param W1={fp.W1}u L1={fp.L1}u W3={fp.W3}u L3={fp.L3}u
.param W5={fp.W5}u L5={fp.L5}u W6={fp.W6}u L6={fp.L6}u
.param W7={fp.W7}u L7={fp.L7}u Wb={fp.Wb}u Lb={fp.Lb}u
.param IREF={fp.Iref}
.param RLOAD={fp.Rload}
"""
    core = "\n" + emit_comparator_core(ms).netlist + "\n"
    lo, hi = vcm - 0.2, vcm + 0.2
    old = ms.block + params_block + core + f"""
Vinp vinp 0 pulse({lo} {hi} 1u 1n 1n 8u 16u)
Vinn vinn 0 {vcm}
.control
set filetype=ascii
tran 10n 10u
meas tran t_plh trig v(vinp) val={vcm+0.05} rise=1 targ v(vout) val=2.5 rise=1
.endc
.end
"""
    new = ms.block + params_block + core + f"""
Vinn vinn 0 {vcm}
Vinp vinp 0 pulse(2.35 2.65 200n 50p 50p 4u 20u)
.control
set filetype=ascii
tran 5n 3u
meas tran t_plh trig v(vinp) val=2.52 rise=1 targ v(vout) val=2.5 fall=1
.endc
.end
"""
    for label, deck in [("OLD_83bcb4d", old), ("CURRENT", new)]:
        ok, out = run_ngspice("* x\n" + deck, timeout=30)
        tp = grab_meas("t_plh", out)
        print(f"  {label}: tp_us={tp*1e6 if tp else None} (commit 99d68df changed deck)")

    print("\n" + "=" * 70)
    print("4. TP MEASUREMENT SANITY — bench assumptions vs perturbations")
    print("=" * 70)
    print("  Current tran deck (_build_tran_deck):")
    print("    Vin step: 2.35V -> 2.65V (300mV overdrive), rise/fall=50ps")
    print("    Vinn fixed at 2.5V (VCM); thresh at vinp=2.52V")
    print("    vout trip at 2.5V (50% of 5V supply); no explicit Cload in netlist")
    print("    Rload only load: sized ~23k, default 50k")

    # Perturb Rload heavier (more realistic external load)
    heavy = ComparatorParams(**{**sized_p, "Rload": 100e3})
    hm = topo.measure(heavy, with_full=True)
    print(f"\n  Sized params + Rload=100k (heavier): tp={hm.values.get('tp_us')}us iq={hm.values.get('iq_uA')}uA")

    light = ComparatorParams(**{**sized_p, "Rload": 10e3})
    lm = topo.measure(light, with_full=True)
    print(f"  Sized params + Rload=10k (lighter):   tp={lm.values.get('tp_us')}us iq={lm.values.get('iq_uA')}uA")

    # designs.jsonl historical loose-profile winner (113uA / 8us)
    loose_p = ComparatorParams(
        W1=45.57921,
        W3=18.54536,
        W5=62.27107,
        W6=56.32233,
        W7=24.78186,
        Wb=36.90479,
        Iref=500e-9,
        Rload=50e3,
    )
    loose_m = topo.measure(loose_p, with_full=True)
    print(f"\n  Loose-profile winner params (113uA case): tp={loose_m.values.get('tp_us')}us iq={loose_m.values.get('iq_uA')}uA")


if __name__ == "__main__":
    main()
