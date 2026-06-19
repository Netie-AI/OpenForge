"""Quick diagnostic: can any seed pass RS-series forge fitness?"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from openanalog.forge.forge_eval import evaluate_forge_fitness
from openanalog.forge.seed_scoring import corpus_report, map_seed_category
from openanalog.forge.topology_detector import infer_topology

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "data" / "seeds_normalized.jsonl"


def main() -> int:
    report = corpus_report()
    if not report.get("exists"):
        print(f"Missing {path}")
        return 1

    by_source: dict[str, list] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if not r.get("sim_validated"):
            continue
        by_source.setdefault(r["source"], []).append(r)

    for source, seeds in by_source.items():
        wins = 0
        sim_ok = 0
        bench = 0
        for r in seeds:
            netlist = r.get("netlist", "")
            inferred = infer_topology(netlist)
            if inferred != "unknown" or map_seed_category(r.get("circuit_type")):
                bench += 1
            ev = evaluate_forge_fitness(netlist, r.get("circuit_type"))
            if ev.get("sim_ok"):
                sim_ok += 1
            if ev["score"] == 1:
                wins += 1
                print(f"WINNER {r['id']} source={source} type={r['circuit_type']} topo={ev['inferred_topology']}")
            elif source == "spice_datasets" and not ev.get("sim_ok"):
                failed = ev.get("failed_checks") or [ev.get("reason")]
                print(f"  FAIL {r['id']}: {failed}")
        print(
            f"{source}: {len(seeds)} sim_validated, benchable={bench}, "
            f"sim_ok={sim_ok}, fitness=1={wins}"
        )

    print(
        f"\nCorpus: total={report['total']} sim_validated={report['sim_validated']} "
        f"benchable={report['benchable']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
