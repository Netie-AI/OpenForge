#!/usr/bin/env python3
"""Phase 1d verification: opamp vs RS321 bar."""
from __future__ import annotations

import re
from collections import Counter

from openanalog.forge.spec_envelopes import DEV_MODE_SPECS
from openanalog.forge.sizer import _passes
from openanalog.forge.topologies.opamp import OpAmpParams, OpAmpTopology
from openanalog.interface.designer import design

RS321 = DEV_MODE_SPECS["opamp"]
BUDGET = 250
SEEDS = [1, 3, 7, 42, 99]


def _device_graph(netlist: str) -> list[str]:
    out = []
    for raw in netlist.splitlines():
        line = raw.strip()
        if not line or line.startswith("*"):
            continue
        if line[0] in "MRCVI":
            norm = re.sub(r"\{[^}]+\}", "{}", line)
            norm = re.sub(r"\s+", " ", norm)
            out.append(norm)
    return out


def _dup_check(netlist: str) -> list[str]:
    names = []
    for line in netlist.splitlines():
        s = line.strip()
        if not s or s.startswith("*") or s.startswith("."):
            continue
        if s[0] in "MRCVDI":
            names.append(s.split()[0])
    return [n for n, c in Counter(names).items() if c > 1]


def _ratio(a: float, b: float) -> str:
    return f"{a / b:.2f}x" if b else "inf"


def main() -> None:
    topo = OpAmpTopology()
    default = topo.default_params()
    dm = topo.measure(default, with_full=True)

    print("=" * 70)
    print("1. DEFAULT vs SEED=42 SIZED")
    print("=" * 70)
    r42 = design(inline_spec=RS321, budget=BUDGET, seed=42, record_kg=False)
    sized_p = r42["params"]

    print("\n(a) DEFAULT metrics:", dm.values)
    print("    params:", default.as_dict())
    print("\n(b) SEED=42 sized metrics:", r42["metrics"])
    print("    meets_all:", r42["meets_all"])
    print("    compliance:", {k: v["pass"] for k, v in r42["compliance"].items()})

    print("\n(c) Key parameter deltas (sized / default):")
    for k in ("W1", "W6", "Cc", "Iref"):
        if k in default.as_dict():
            dv, sv = default.as_dict()[k], sized_p[k]
            print(f"    {k}: {dv:.6g} -> {sv:.6g}  ({_ratio(sv, dv)})")

    nl_def = topo.emit_netlist(default)
    nl_sized = topo.emit_netlist(OpAmpParams(**{k: sized_p[k] for k in default.as_dict()}))
    print(f"\n(d) Structure identical: {_device_graph(nl_def) == _device_graph(nl_sized)}")
    dups = _dup_check(r42["netlist"])
    print(f"    Duplicate instances (seed=42 netlist): {dups if dups else 'NONE'}")

    print("\n(e) RS321 target-mode tolerance check (_passes tol=0.05):")
    gbp = r42["metrics"].get("gbp_MHz")
    print(f"    gbp measured={gbp} target=1.1 pass={_passes(gbp, 1.1, 'target')} (band 1.045–1.155 MHz)")

    print("\n" + "=" * 70)
    print("2. SEED SENSITIVITY (budget=250)")
    print("=" * 70)
    pass_n = 0
    for seed in SEEDS:
        r = design(inline_spec=RS321, budget=BUDGET, seed=seed, record_kg=False)
        ok = r["meets_all"]
        pass_n += int(ok)
        m = r["metrics"]
        fail = [k for k, v in r["compliance"].items() if v.get("pass") is False]
        print(
            f"  seed={seed:2d} meets_all={ok} "
            f"AOL={m.get('aol_dB'):.1f} GBP={m.get('gbp_MHz'):.3f} "
            f"PM={m.get('pm_deg'):.1f} Iq={m.get('iq_uA'):.1f}uA "
            f"fail={fail or '-'}"
        )
    print(f"\n  Pass rate: {pass_n}/{len(SEEDS)}")

    print("\n" + "=" * 70)
    print("3. DEFAULT params vs RS321 bar")
    print("=" * 70)
    rd = design(inline_spec=RS321, budget=1, seed=42, record_kg=False)
    # budget=1 won't size; measure defaults via single sample
    from openanalog.forge.sizer import score_design
    spec = rd["spec"]
    cand = score_design(dm, spec["targets"], measurable=topo.measurable_specs(), weights=topo.spec_weights)
    print(f"  default meets_all (direct measure): {cand.meets_all}")
    print(f"  default compliance:", {k: v["pass"] for k, v in cand.per_spec.items()})


if __name__ == "__main__":
    main()
