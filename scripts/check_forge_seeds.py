"""Quick diagnostic: can any seed actually pass forge fitness?"""
import json
from pathlib import Path

from openanalog.forge.fitness import score_fitness
from openanalog.forge.simulator import simulate

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "data" / "seeds_normalized.jsonl"

by_source: dict[str, list] = {}
for line in path.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    r = json.loads(line)
    by_source.setdefault(r["source"], []).append(r)

for source, seeds in by_source.items():
    wins = 0
    sim_ok = 0
    for r in seeds:
        sim = simulate(r["netlist"])
        fit = score_fitness(r["circuit_type"], sim)
        if sim.ok:
            sim_ok += 1
        if fit["score"] == 1:
            wins += 1
            print(f"WINNER {r['id']} source={source} type={r['circuit_type']}")
        elif source == "spice_datasets" and not sim.ok:
            print(f"  FAIL {r['id']}: {(sim.error or sim.raw)[:300]}")
    print(f"{source}: {len(seeds)} seeds, sim_ok={sim_ok}, fitness=1={wins}")
