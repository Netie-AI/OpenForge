from __future__ import annotations

import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.progress import Progress

from openanalog import claude
from openanalog.confidence import kg_tier
from openanalog.config import FORGE_STATE, SEEDS_NORMALIZED, ensure_dirs
from openanalog.forge.dataset_writer import DatasetWriter
from openanalog.forge.fitness import score_fitness
from openanalog.forge.generator import mutate_netlist, MutationMode
from openanalog.forge.knowledge_graph import KnowledgeGraph
from openanalog.forge.mutator import directed_mutate
from openanalog.forge.simulator import is_simulatable, simulate

console = Console()

FORGE_STATS: dict = {
    "sims": 0,
    "winners": 0,
    "by_topology": {},
}


def _load_seeds(topology: str | None) -> list[dict]:
    path = SEEDS_NORMALIZED
    if not path.exists():
        return [
            {
                "id": "demo_0",
                "circuit_type": topology or "tia",
                "netlist": "* demo\nVDD vdd 0 DC 1.8\nR1 out in 10k\nC1 out 0 1p\n.end",
            }
        ]
    seeds = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if topology and rec.get("circuit_type") != topology:
            continue
        if rec.get("netlist") and is_simulatable(rec["netlist"]):
            seeds.append(rec)
    if not seeds:
        console.print(
            "[yellow]No simulatable seeds (need standard SPICE with V/I sources). "
            "AnalogGenie/Masala syntax is skipped.[/yellow]"
        )
    return seeds or [{"id": "fallback", "circuit_type": topology or "tia", "netlist": ".end\n"}]


def _update_stats(topo: str, won: bool, stats: dict) -> None:
    stats["sims"] += 1
    if won:
        stats["winners"] += 1
    bt = stats["by_topology"].setdefault(topo, {"sims": 0, "winners": 0})
    bt["sims"] += 1
    if won:
        bt["winners"] += 1


def _load_forge_state() -> dict[str, Any]:
    if FORGE_STATE.exists():
        return json.loads(FORGE_STATE.read_text(encoding="utf-8"))
    return {"completed": 0, "target": 0, "stats": dict(FORGE_STATS)}


def _save_forge_state(state: dict[str, Any]) -> None:
    FORGE_STATE.parent.mkdir(parents=True, exist_ok=True)
    FORGE_STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _forge_worker(args: tuple[str, str, str, list[str]]) -> dict[str, Any] | None:
    net, topo, seed_id, analyses = args
    _ = analyses
    try:
        child = mutate_netlist(net, MutationMode.RANDOM)
    except ValueError:
        return None
    sim = simulate(child, circuit_type=topo)
    fit = score_fitness(topo, sim)
    return {
        "topo": topo,
        "seed_id": seed_id,
        "child": child,
        "sim": {
            "bw_MHz": sim.bw_3db_MHz,
            "gain_dB": sim.gain_dB,
            "power_mW": sim.power_mW,
            "PM_deg": sim.phase_margin,
        },
        "fit": fit,
        "won": fit["score"] == 1,
    }


def _process_result(
    result: dict[str, Any],
    *,
    generation: int,
    stats: dict,
    writer: DatasetWriter,
    kg: KnowledgeGraph,
    stagnant: dict[str, int],
) -> None:
    topo = result["topo"]
    fit = result["fit"]
    won = result["won"]
    _update_stats(topo, won, stats)

    writer.write(
        fitness=fit["score"],
        topology=topo,
        netlist=result["child"],
        sim_result=result["sim"],
        generation=generation,
        topology_id=result["seed_id"],
        pass_margins=fit["margin_per_check"],
    )

    if won:
        conf = 0.88
        if stats["winners"] % 20 == 0:
            try:
                rev = claude.review_netlist(topo, result["child"], result["sim"])
                conf = float(rev.get("confidence_10", 8)) / 10.0
            except Exception:
                pass
        kg.add_node(
            topo,
            result["child"],
            {},
            result["sim"],
            fitness_pass_rate=1.0,
            generation=generation,
            parent_id=result["seed_id"],
            tier=kg_tier(conf),
        )
        stagnant[topo] = 0
    else:
        stagnant[topo] = stagnant.get(topo, 0) + 1
        if stagnant[topo] < 50:
            try:
                directed_mutate(result["child"], fit["failed_checks"], fit["margin_per_check"])
            except ValueError:
                pass


def run_forge(
    *,
    topology: str | None = None,
    n: int = 100,
    all_topologies: bool = False,
    workers: int = 4,
    reset: bool = False,
    dry_run: bool = False,
) -> None:
    ensure_dirs()
    if reset and FORGE_STATE.exists():
        FORGE_STATE.unlink()

    state = _load_forge_state()
    stats = state.get("stats") or dict(FORGE_STATS)
    if not stats.get("by_topology"):
        stats["by_topology"] = {}
    start = int(state.get("completed", 0)) if not reset else 0
    if start >= n:
        console.print(f"[yellow]Forge already complete ({start}/{n}). Use --reset to restart.[/yellow]")
        return

    seeds = _load_seeds(None if all_topologies else topology)
    kg = KnowledgeGraph()
    kg.load()
    writer = DatasetWriter()
    stagnant: dict[str, int] = {}
    workers = max(1, workers)

    with Progress() as progress:
        task = progress.add_task("Forge simulations", total=n, completed=start)
        i = start
        while i < n:
            batch_end = min(i + workers, n)
            batch_jobs: list[tuple[str, str, str, list[str]]] = []
            for j in range(i, batch_end):
                seed = seeds[j % len(seeds)]
                topo = seed.get("circuit_type", topology or "unknown")
                analyses = ["op", "ac", "tran"] if topo == "charge_pump" else ["op", "ac"]
                batch_jobs.append((seed["netlist"], topo, seed.get("id", "seed"), analyses))

            if dry_run:
                for j, job in enumerate(batch_jobs):
                    _update_stats(job[1], False, stats)
                    progress.advance(task)
                i = batch_end
            elif workers == 1:
                for j, job in enumerate(batch_jobs):
                    result = _forge_worker(job)
                    if result:
                        _process_result(
                            result,
                            generation=i + j,
                            stats=stats,
                            writer=writer,
                            kg=kg,
                            stagnant=stagnant,
                        )
                    progress.advance(task)
                i = batch_end
            else:
                with ProcessPoolExecutor(max_workers=workers) as pool:
                    futures = {pool.submit(_forge_worker, job): job for job in batch_jobs}
                    for fut in as_completed(futures):
                        result = fut.result()
                        if result:
                            _process_result(
                                result,
                                generation=i,
                                stats=stats,
                                writer=writer,
                                kg=kg,
                                stagnant=stagnant,
                            )
                        progress.advance(task)
                i = batch_end

            if stats["sims"] % 100 == 0 and stats["sims"] > 0:
                kg.prune()
                kg.save()
                _save_forge_state(
                    {
                        "completed": i,
                        "target": n,
                        "topology": topology,
                        "all_topologies": all_topologies,
                        "stats": stats,
                    }
                )

    kg.save()
    _save_forge_state(
        {
            "completed": n,
            "target": n,
            "topology": topology,
            "all_topologies": all_topologies,
            "stats": stats,
        }
    )
    console.print(f"Done: {stats['sims']} sims, {stats['winners']} winners")


def forge_status() -> dict:
    if FORGE_STATE.exists():
        data = json.loads(FORGE_STATE.read_text(encoding="utf-8"))
        return data.get("stats", FORGE_STATS)
    return FORGE_STATS
