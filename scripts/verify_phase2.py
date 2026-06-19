#!/usr/bin/env python3
"""Phase 2 verification: seeds_normalized.jsonl wired into forge fitness loop."""
from __future__ import annotations

import sys

from openanalog.forge.seed_scoring import (
    corpus_report,
    load_normalized_seeds,
    run_seed_scoring,
    score_seed_record,
    select_benchable_seeds,
)

MIN_SIM_VALIDATED = 500
SAMPLE_SCORE = 5


def main() -> int:
    report = corpus_report()
    print("=" * 70)
    print("Phase 2 — seed corpus")
    print("=" * 70)

    if not report.get("exists"):
        print(f"MISSING: {report.get('path', 'data/seeds_normalized.jsonl')}")
        print("Run: python -m openanalog load-seeds")
        return 1

    total = report["total"]
    sim_ok = report["sim_validated"]
    bench = report["benchable_sim_validated"]
    pct = 100 * sim_ok / total if total else 0

    print(f"  path:            {report['path']}")
    print(f"  total:           {total}")
    print(f"  sim_validated:   {sim_ok} ({pct:.1f}%)")
    print(f"  benchable:       {report['benchable']} ({report['benchable_sim_validated']} sim_validated)")
    print(f"  by_topology:     {report['by_inferred_topology']}")
    print(f"  dialect:         {report['dialect_breakdown']}")

    if sim_ok < MIN_SIM_VALIDATED:
        print(f"\nFAIL: sim_validated={sim_ok} < {MIN_SIM_VALIDATED} (Phase 2 exit bar)")
        return 1

    print("\n" + "=" * 70)
    print(f"Sample seed scoring ({SAMPLE_SCORE} benchable netlists → evaluate_forge_fitness)")
    print("=" * 70)

    seeds = select_benchable_seeds(
        load_normalized_seeds(sim_validated_only=True),
        limit=SAMPLE_SCORE,
    )
    if not seeds:
        print("FAIL: no benchable sim-validated seeds")
        return 1

    scored = sim_pass = fitness1 = 0
    for rec in seeds:
        result = score_seed_record(rec)
        if result is None:
            continue
        scored += 1
        if result["sim_ok"]:
            sim_pass += 1
        if result["won"]:
            fitness1 += 1
        print(
            f"  {rec['id']}: topo={result['topo']} "
            f"sim_ok={result['sim_ok']} score={result['fit']['score']} "
            f"failed={result['fit']['failed_checks'][:3]}"
        )

    print(f"\n  sample_scored={scored} sim_ok={sim_pass} fitness=1={fitness1}")
    print("  (fitness=1 on raw seeds is rare — wiring is the gate, not RS pass rate)")

    print("\n" + "=" * 70)
    print("Forge loop wiring smoke (dry run_seed_scoring limit=2)")
    print("=" * 70)
    counts = run_seed_scoring(limit=2)
    print(f"  scored={counts['scored']} benchable={counts['benchable']} sim_ok={counts['sim_ok']}")

    if counts["scored"] < 1:
        print("FAIL: run_seed_scoring produced no results")
        return 1

    print("\nPhase 2 PASS — corpus feeds evaluate_forge_fitness via openanalog/forge/seed_scoring.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
