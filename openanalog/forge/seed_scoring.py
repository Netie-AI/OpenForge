"""Score sim-validated seeds through the RS-series forge fitness gate (Phase 2)."""

from __future__ import annotations

import json
from typing import Any

from openanalog.config import SEEDS_NORMALIZED
from openanalog.forge.forge_eval import evaluate_forge_fitness
from openanalog.forge.topology_detector import infer_topology, resolve_forge_topology
from openanalog.ingestion.converter import extract_params
from openanalog.ingestion.dialect import dialect_breakdown

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


def map_seed_category(raw: str | None) -> str | None:
    if not raw:
        return None
    return _SEED_TYPE_MAP.get(raw.lower().replace("-", "_"))


def load_normalized_seeds(
    *,
    topology: str | None = None,
    sim_validated_only: bool = True,
    benchable_only: bool = False,
) -> list[dict[str, Any]]:
    """Load records from ``seeds_normalized.jsonl``."""
    if not SEEDS_NORMALIZED.exists():
        return []
    seeds: list[dict[str, Any]] = []
    for line in SEEDS_NORMALIZED.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if sim_validated_only and not rec.get("sim_validated"):
            continue
        if not rec.get("netlist"):
            continue
        cat = map_seed_category(rec.get("circuit_type"))
        inferred = infer_topology(rec["netlist"])
        if topology and cat != topology and inferred != topology:
            continue
        if benchable_only and inferred == "unknown" and cat is None:
            continue
        seeds.append(rec)
    return seeds


def group_seed_hints(seeds: list[dict[str, Any]]) -> dict[str, list[dict[str, float]]]:
    """Extract ``.param`` hints grouped by mapped forge category."""
    from openanalog.forge.spec_envelopes import DEV_MODE_SPECS

    grouped: dict[str, list[dict[str, float]]] = {c: [] for c in DEV_MODE_SPECS}
    for rec in seeds:
        cat = map_seed_category(rec.get("circuit_type"))
        if cat not in grouped:
            continue
        hints = extract_params(rec.get("netlist", ""))
        if hints:
            grouped[cat].append(hints)
    return grouped


def score_seed_record(rec: dict[str, Any]) -> dict[str, Any] | None:
    """Evaluate one seed netlist on the RS-series bar (``evaluate_forge_fitness``)."""
    netlist = rec.get("netlist", "")
    if not netlist.strip():
        return None
    circuit_type = rec.get("circuit_type")
    ev = evaluate_forge_fitness(netlist, circuit_type)
    topo = ev["inferred_topology"]
    return {
        "topo": topo,
        "seed_topo": map_seed_category(circuit_type) or topo,
        "seed_id": rec.get("id", "seed_unknown"),
        "child": netlist,
        "params": extract_params(netlist),
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
            k: v.get("pass")
            for k, v in ev.get("per_spec", {}).items()
            if v.get("pass") is not None
        },
    }


def corpus_report() -> dict[str, Any]:
    """Summarize the normalized seed corpus for Phase 2 verification."""
    if not SEEDS_NORMALIZED.exists():
        return {"exists": False, "total": 0, "sim_validated": 0, "benchable": 0}

    total = sim_validated = benchable = benchable_validated = 0
    netlists: list[str] = []
    by_inferred: dict[str, int] = {}
    by_label: dict[str, int] = {}

    for line in SEEDS_NORMALIZED.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        total += 1
        netlists.append(rec.get("netlist", ""))
        is_valid = bool(rec.get("sim_validated"))
        if is_valid:
            sim_validated += 1
        inferred = infer_topology(rec.get("netlist", ""))
        if inferred != "unknown":
            benchable += 1
            if is_valid:
                benchable_validated += 1
                by_inferred[inferred] = by_inferred.get(inferred, 0) + 1
        label = map_seed_category(rec.get("circuit_type")) or rec.get("circuit_type", "unknown")
        by_label[label] = by_label.get(label, 0) + 1

    return {
        "exists": True,
        "path": str(SEEDS_NORMALIZED),
        "total": total,
        "sim_validated": sim_validated,
        "benchable": benchable,
        "benchable_sim_validated": benchable_validated,
        "by_inferred_topology": by_inferred,
        "by_circuit_type_label": by_label,
        "dialect_breakdown": dialect_breakdown(netlists),
    }


def select_benchable_seeds(
    seeds: list[dict[str, Any]],
    *,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Prefer seeds whose netlist resolves to a registered bench topology."""
    benchable: list[dict[str, Any]] = []
    for rec in seeds:
        netlist = rec.get("netlist", "")
        inferred = resolve_forge_topology(netlist, rec.get("circuit_type"))
        if inferred != "unknown":
            benchable.append(rec)
    if limit is not None:
        return benchable[:limit]
    return benchable


def run_seed_scoring(
    *,
    limit: int | None = 25,
    topology: str | None = None,
    process_result=None,
    generation_offset: int = 0,
) -> dict[str, int]:
    """
    Score seed netlists through ``evaluate_forge_fitness`` and optionally persist.

    Returns counts: ``scored``, ``benchable``, ``fitness_1``, ``sim_ok``.
    """
    seeds = load_normalized_seeds(topology=topology, sim_validated_only=True)
    targets = select_benchable_seeds(seeds, limit=limit)
    counts = {"scored": 0, "benchable": len(targets), "fitness_1": 0, "sim_ok": 0}

    for i, rec in enumerate(targets):
        result = score_seed_record(rec)
        if result is None:
            continue
        counts["scored"] += 1
        if result["won"]:
            counts["fitness_1"] += 1
        if result["sim_ok"]:
            counts["sim_ok"] += 1
        if process_result is not None:
            process_result(result, generation=generation_offset + i)

    return counts
