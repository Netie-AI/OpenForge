from __future__ import annotations

import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Any

from rich.console import Console
from rich.progress import Progress

from openanalog import claude
from openanalog.confidence import kg_tier
from openanalog.config import FORGE_STATE, SEEDS_NORMALIZED, ensure_dirs
from openanalog.forge.dataset_writer import DatasetWriter
from openanalog.forge.forge_eval import evaluate_topology_params
from openanalog.forge.knowledge_graph import KnowledgeGraph
from openanalog.forge.param_mutator import apply_seed_hints, mutate_params, opamp_warm_start_params
from openanalog.forge.spec_envelopes import DEV_MODE_SPECS
from openanalog.forge.topologies import get_topology
from openanalog.ingestion.converter import extract_params

console = Console()

FORGE_STATS: dict = {
    "sims": 0,
    "winners": 0,
    "by_topology": {},
}

FORGE_CATEGORIES = tuple(DEV_MODE_SPECS.keys())

_SEED_TYPE_MAP: dict[str, str] = {
    "opamp": "opamp",
    "op_amp": "opamp",
    "amplifier": "opamp",
    "diff_amp": "opamp",
    "ota": "opamp",
    "comparator": "comparator",
    "switch": "switch",
    "analog_switch": "switch",
    "charge_pump": "charge_pump",
    "ldo": "ldo",
    "linear_regulator": "ldo",
}


def _map_seed_category(raw: str | None) -> str | None:
    if not raw:
        return None
    return _SEED_TYPE_MAP.get(raw.lower().replace("-", "_"))


def _load_seeds(topology: str | None) -> list[dict]:
    path = SEEDS_NORMALIZED
    if not path.exists():
        return []
    seeds = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        cat = _map_seed_category(rec.get("circuit_type"))
        if topology and cat != topology:
            continue
        if rec.get("netlist"):
            seeds.append(rec)
    return seeds


def _group_seed_hints(seeds: list[dict]) -> dict[str, list[dict[str, float]]]:
    grouped: dict[str, list[dict[str, float]]] = {c: [] for c in FORGE_CATEGORIES}
    for rec in seeds:
        cat = _map_seed_category(rec.get("circuit_type"))
        if cat not in grouped:
            continue
        hints = extract_params(rec.get("netlist", ""))
        if hints:
            grouped[cat].append(hints)
    return grouped


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


def _forge_worker(args: tuple[str, dict[str, float], str, int, int]) -> dict[str, Any] | None:
    category, seed_hints, seed_id, generation, total_n = args
    try:
        topology = get_topology(category)
        if category == "opamp":
            base = topology.params_from_dict(opamp_warm_start_params())
        else:
            base = apply_seed_hints(topology.default_params(), seed_hints, topology)
        mutated = mutate_params(
            topology,
            base,
            seed=generation,
            generation=generation,
            total=total_n,
            category=category,
        )
        ev = evaluate_topology_params(category, mutated)
        netlist = topology.emit_netlist(mutated)
    except (ValueError, KeyError):
        return None
    return {
        "topo": ev["inferred_topology"],
        "seed_topo": category,
        "seed_id": seed_id,
        "child": netlist,
        "params": mutated.as_dict() if hasattr(mutated, "as_dict") else {},
        "sim": ev.get("measured", {}),
        "fit": {
            "score": ev["score"],
            "failed_checks": ev["failed_checks"],
            "margin_per_check": ev["margin_per_check"],
        },
        "per_spec": ev.get("per_spec", {}),
        "won": ev["score"] == 1,
        "sim_ok": ev.get("sim_ok", False),
        "compliance": {
            k: v.get("pass") for k, v in ev.get("per_spec", {}).items() if v.get("pass") is not None
        },
    }


def _process_result(
    result: dict[str, Any],
    *,
    generation: int,
    stats: dict,
    writer: DatasetWriter,
    kg: KnowledgeGraph,
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
        params=result.get("params"),
        per_spec=result.get("per_spec"),
        compliance=result.get("compliance"),
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
            result.get("params", {}),
            result["sim"],
            fitness_pass_rate=1.0,
            generation=generation,
            parent_id=result["seed_id"],
            tier=kg_tier(conf),
        )


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

    if topology:
        categories = [topology]
    elif all_topologies:
        categories = list(FORGE_CATEGORIES)
    else:
        categories = list(FORGE_CATEGORIES)

    seeds = _load_seeds(None if all_topologies else topology)
    hint_groups = _group_seed_hints(seeds)
    if seeds:
        console.print(f"[dim]Loaded {len(seeds)} seeds for parameter hints (not netlist mutation)[/dim]")
    else:
        console.print("[dim]No seed file — mutating topology default params only[/dim]")

    kg = KnowledgeGraph()
    kg.load()
    writer = DatasetWriter()
    workers = max(1, workers)

    with Progress() as progress:
        task = progress.add_task("Forge simulations", total=n, completed=start)
        i = start
        while i < n:
            batch_end = min(i + workers, n)
            batch_jobs: list[tuple[str, dict[str, float], str, int, int]] = []
            for j in range(i, batch_end):
                category = categories[(i + j) % len(categories)]
                hints_list = hint_groups.get(category, [])
                hints = hints_list[(i + j) % len(hints_list)] if hints_list else {}
                seed_id = f"topo_{category}_{(i + j) % max(1, len(hints_list) or 1)}"
                batch_jobs.append((category, hints, seed_id, i + j, n))

            if dry_run:
                for job in batch_jobs:
                    _update_stats(job[0], False, stats)
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
    console.print(
        f"Done: {stats['sims']} sims, {stats['winners']} winners "
        f"(RS-series bar — topology param mutation)"
    )


def forge_status() -> dict:
    if FORGE_STATE.exists():
        data = json.loads(FORGE_STATE.read_text(encoding="utf-8"))
        return data.get("stats", FORGE_STATS)
    return FORGE_STATS
