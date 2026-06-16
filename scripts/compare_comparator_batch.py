#!/usr/bin/env python3
"""Deterministic comparator forge batch — no corpus writes, for pre/post refactor diff."""

from __future__ import annotations

import json
import statistics
import sys
from typing import Any

from openanalog.forge.forge_eval import evaluate_topology_params
from openanalog.forge.param_mutator import apply_seed_hints, mutate_params
from openanalog.forge.runner import _forge_worker
from openanalog.forge.topologies import get_topology

N = 50
SPEC_KEYS = ("tp_us", "vos_mV", "iq_uA", "trise_ns", "tfall_ns")


def _summarize(vals: list[float]) -> dict[str, float | int]:
    if not vals:
        return {"n": 0}
    return {
        "n": len(vals),
        "min": min(vals),
        "max": max(vals),
        "median": statistics.median(vals),
        "mean": statistics.mean(vals),
    }


def run_batch(*, via_worker: bool = True) -> dict[str, Any]:
    topology = get_topology("comparator")
    base = apply_seed_hints(topology.default_params(), {}, topology)
    per_gen: list[dict[str, Any]] = []
    winners: list[dict[str, Any]] = []
    loser_count = 0

    for gen in range(N):
        if via_worker:
            job = ("comparator", {}, f"topo_comparator_{gen}", gen, N)
            result = _forge_worker(job)
            if result is None:
                loser_count += 1
                per_gen.append({"gen": gen, "won": False, "measured": {}})
                continue
            won = result["won"]
            measured = result["sim"]
        else:
            mutated = mutate_params(
                topology, base, seed=gen, generation=gen, total=N, category="comparator"
            )
            ev = evaluate_topology_params("comparator", mutated)
            won = ev["score"] == 1
            measured = ev["measured"]

        per_gen.append({"gen": gen, "won": won, "measured": measured})
        if won:
            winners.append(measured)
        else:
            loser_count += 1

    spec_stats = {
        key: _summarize([w[key] for w in winners if w.get(key) is not None])
        for key in SPEC_KEYS
    }
    return {
        "n": N,
        "winners": len(winners),
        "losers": loser_count,
        "win_rate": len(winners) / N,
        "spec_stats": spec_stats,
        "winner_specs": winners,
        "per_gen": per_gen,
    }


def main() -> None:
    label = sys.argv[1] if len(sys.argv) > 1 else "post"
    out = run_batch(via_worker=True)
    out["label"] = label
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
