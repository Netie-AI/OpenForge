#!/usr/bin/env python3
"""Dump per-seed fitness scores to stdout as JSON (zero-trust checkpoint)."""
from __future__ import annotations

import json
import sys

from openanalog.forge.seed_scoring import load_normalized_seeds, score_seed_record, select_benchable_seeds


def main() -> int:
    seeds = select_benchable_seeds(load_normalized_seeds(sim_validated_only=True))
    rows = []
    fitness1 = 0
    for rec in seeds:
        result = score_seed_record(rec)
        if result is None:
            continue
        row = {
            "id": rec.get("id"),
            "circuit_type": rec.get("circuit_type"),
            "inferred_topology": result.get("topo"),
            "fitness_score": result["fit"]["score"],
            "won": result["won"],
            "sim_ok": result["sim_ok"],
            "failed_checks": result["fit"].get("failed_checks", []),
        }
        rows.append(row)
        if result["won"]:
            fitness1 += 1
    out = {
        "total_benchable_sim_validated": len(seeds),
        "total_scored": len(rows),
        "fitness_1_count": fitness1,
        "fitness_1_rate": (fitness1 / len(rows)) if rows else None,
        "seeds": rows,
    }
    json.dump(out, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
