#!/usr/bin/env python3
"""Harness gate report — fitness=1 pass rates across corpus, KG, and forge."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WINNERS = ROOT / "data" / "training" / "winners.jsonl"
LOSERS = ROOT / "data" / "training" / "losers.jsonl"
FORGE_STATE = ROOT / "data" / "forge_state.json"
KG_STATS = ROOT / "data" / "knowledge_graph" / "graph.gpickle"
TARGET_GATE_PCT = 50.0


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> None:
    winners = _load_jsonl(WINNERS)
    losers = _load_jsonl(LOSERS)

    w_f1 = sum(1 for w in winners if w.get("fitness") == 1)
    l_f1 = sum(1 for w in losers if w.get("fitness") == 1)

    total_sims = len(winners) + len(losers)
    total_f1 = w_f1 + l_f1
    harness_pct = (100.0 * total_f1 / total_sims) if total_sims else 0.0

    print("=== HARNESS GATE REPORT (fitness=1 = gold standard) ===\n")
    print(f"Winners:  {len(winners)} ({w_f1} fitness=1)")
    print(f"Losers:   {len(losers)}")
    print(f"Total:    {total_sims} sims, {total_f1} fitness=1")
    print(f"Harness pass rate: {harness_pct:.1f}%  (target > {TARGET_GATE_PCT}%)")

    by_topo: dict[str, dict] = {}
    for w in winners:
        t = w.get("topology", "unknown")
        by_topo.setdefault(t, {"winners": 0, "f1": 0})
        by_topo[t]["winners"] += 1
        if w.get("fitness") == 1:
            by_topo[t]["f1"] += 1

    print("\nBy topology (winners.jsonl):")
    for topo in sorted(by_topo):
        d = by_topo[topo]
        print(f"  {topo}: {d['winners']} winners, {d['f1']} fitness=1")

    if FORGE_STATE.exists():
        st = json.loads(FORGE_STATE.read_text(encoding="utf-8"))
        stats = st.get("stats", {})
        sims = stats.get("sims", 0)
        f1 = stats.get("winners", 0)
        forge_pct = (100.0 * f1 / sims) if sims else 0.0
        print(f"\nForge state: {sims} sims, {f1} winners ({forge_pct:.2f}% hit rate)")
        for topo, bt in sorted(stats.get("by_topology", {}).items()):
            ts = bt.get("sims", 0)
            tw = bt.get("winners", 0)
            rate = (100.0 * tw / ts) if ts else 0.0
            print(f"  forge {topo}: {tw}/{ts} ({rate:.2f}%)")

    if KG_STATS.exists():
        print(f"\nKG graph: {KG_STATS} exists")
    else:
        print("\nKG graph: not yet built")

    print(f"\n=== GATE STATUS: {'PASS' if harness_pct >= TARGET_GATE_PCT else 'BELOW TARGET'} ===")
    if harness_pct < TARGET_GATE_PCT:
        print("Action: run forge loop to grow fitness=1 corpus:")
        print("  python -m openanalog forge --n 500 --workers 4")
        sys.exit(2)
    print("CHECK PASSED — harness gate above target")


if __name__ == "__main__":
    main()
