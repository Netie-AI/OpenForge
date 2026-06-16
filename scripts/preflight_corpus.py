#!/usr/bin/env python3
"""Corpus diversity pre-flight check before Lambda finetuning."""
import json
import statistics
import sys
from pathlib import Path

WINNERS = Path("data/training/winners.jsonl")

# Specs that may be None without blocking finetune (see docs/STATUS.md).
OPTIONAL_SPECS: dict[str, set[str]] = {
    "comparator": {"tfall_ns"},
}

if not WINNERS.exists():
    print("MISSING winners.jsonl")
    sys.exit(1)

winners = [json.loads(l) for l in WINNERS.read_text().splitlines() if l.strip()]
stop_reasons: list[str] = []

for topo in ["opamp", "comparator", "switch", "ldo", "charge_pump"]:
    subset = [w for w in winners if w["topology"] == topo]
    if not subset:
        print(f"{topo}: 0 winners — MISSING")
        stop_reasons.append(f"{topo}: missing")
        continue
    print(f"\n=== {topo}: {len(subset)} winners ===")
    nl_lens = [len(w.get("netlist", "")) for w in subset]
    print(
        f"  netlist_len: min={min(nl_lens)} max={max(nl_lens)} "
        f"mean={sum(nl_lens) // len(nl_lens)}"
    )
    short = sum(1 for ln in nl_lens if ln < 200)
    if short:
        print(f"  STOP: {short} winners with netlist_len < 200")
        stop_reasons.append(f"{topo}: short netlists")

    all_keys: set[str] = set()
    for w in subset:
        all_keys.update(w.get("params", {}).keys())
    param_stds: dict[str, float] = {}
    shown = 0
    for k in sorted(all_keys):
        vals = [w["params"][k] for w in subset if k in w.get("params", {})]
        if len(vals) > 1:
            std = statistics.stdev(vals)
            param_stds[k] = std
            if shown < 3 or (topo == "opamp" and k == "W1"):
                print(f"  {k}: min={min(vals):.4f} max={max(vals):.4f} std={std:.4f}")
                shown += 1

    if param_stds and all(s == 0.0 for s in param_stds.values()):
        print("  STOP: all params have std=0 (degenerate)")
        stop_reasons.append(f"{topo}: degenerate params")

    if topo == "opamp" and "W1" in param_stds and param_stds["W1"] < 0.1:
        print(f"  STOP: opamp W1 std={param_stds['W1']:.4f} < 0.1")
        stop_reasons.append("opamp: W1 diversity insufficient")

    optional = OPTIONAL_SPECS.get(topo, set())
    none_counts: dict[str, int] = {}
    blocking_none = 0
    for w in subset:
        for k, v in w.get("measured_specs", {}).items():
            if v is None:
                none_counts[k] = none_counts.get(k, 0) + 1
                if k not in optional:
                    blocking_none += 1
    if none_counts:
        opt_only = all(k in optional for k in none_counts)
        label = "optional None specs" if opt_only else "WARN None specs"
        print(f"  {label}: {none_counts}")
        if blocking_none:
            stop_reasons.append(f"{topo}: None in required measured_specs")
    else:
        print("  measured_specs: all non-None OK")

print("\n=== STOP SUMMARY ===")
if stop_reasons:
    for r in stop_reasons:
        print(f"  BLOCKED: {r}")
    sys.exit(1)
print("  ALL CHECKS PASSED")
