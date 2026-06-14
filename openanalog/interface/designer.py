"""
openanalog/interface/designer.py

End-to-end: datasheet/spec -> structured spec -> sized topology -> validated
netlist + compliance report -> knowledge-graph node.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable

from openanalog.config import DATA_DIR
from openanalog.eda.footprints import attach_eda_metadata
from openanalog.forge.sizer import Candidate, size
from openanalog.forge.topologies import get_topology
from openanalog.interface.datasheet import detect_category, extract_specs, parse_inline_spec


def candidate_to_result(spec: dict[str, Any], cand: Candidate, topology) -> dict[str, Any]:
    supply_V = float(spec.get("supply_V", 5.0))
    cload_F = float(spec.get("cload_F", 10e-12))
    netlist = topology.emit_netlist(cand.params, supply_V=supply_V, cload_F=cload_F)
    package = topology.package_hint(spec)
    return {
        "spec": spec,
        "category": topology.circuit_type,
        "topology": topology.topology_name,
        "supply_V": supply_V,
        "package": package,
        "meets_all": cand.meets_all,
        "score": round(cand.score, 4),
        "metrics": cand.metrics.as_dict(),
        "compliance": cand.per_spec,
        "params": {
            k: (round(v, 9) if isinstance(v, float) else v)
            for k, v in cand.params.as_dict().items()
        },
        "devices": topology.device_list(cand.params),
        "netlist": netlist,
        "warnings": list(cand.metrics.warnings),
        "measurable_specs": sorted(topology.measurable_specs()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def design(
    *,
    text: str | None = None,
    inline_spec: str | None = None,
    spec: dict[str, Any] | None = None,
    category: str | None = None,
    budget: int = 200,
    use_claude: bool = False,
    seed: int = 1,
    progress: Callable[[int, int, float], None] | None = None,
    record_kg: bool = True,
) -> dict[str, Any]:
    if spec is None:
        if inline_spec:
            spec = parse_inline_spec(inline_spec, category=category)
        elif text:
            cat = category or detect_category(text)
            spec = extract_specs(text, use_claude=use_claude, category=cat)
        else:
            raise ValueError("Provide text, inline_spec, or spec")

    if category:
        spec["circuit_type"] = category

    circuit_type = spec.get("circuit_type", "opamp")
    try:
        topology = get_topology(circuit_type)
    except ValueError:
        topology = get_topology("opamp")
        spec.setdefault("notes", []).append(f"unknown type '{circuit_type}'; fell back to opamp")

    if not spec.get("targets"):
        raise ValueError("No design targets could be extracted from the input")

    cand = size(topology, spec, budget=budget, seed=seed, progress=progress)
    result = candidate_to_result(spec, cand, topology)
    result = attach_eda_metadata(result)

    if record_kg:
        try:
            _record_kg(result)
        except Exception as e:
            result["warnings"].append(f"KG record skipped: {e}")
    _log_design(result)
    return result


def _record_kg(result: dict[str, Any]) -> None:
    from openanalog.confidence import kg_tier
    from openanalog.forge.knowledge_graph import KnowledgeGraph

    kg = KnowledgeGraph()
    kg.load()
    conf = 0.92 if result["meets_all"] else 0.6
    kg.add_node(
        result["category"],
        result["netlist"],
        result["params"],
        result["metrics"],
        fitness_pass_rate=1.0 if result["meets_all"] else 0.5,
        generation=0,
        tier=kg_tier(conf),
        paper_sources=[result["spec"].get("part", "spec")],
        category=result["category"],
    )
    kg.save()


def _log_design(result: dict[str, Any]) -> None:
    out = DATA_DIR / "designs.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    slim = {k: v for k, v in result.items() if k not in ("netlist", "kicad_sym_stub")}
    with out.open("a", encoding="utf-8") as f:
        f.write(json.dumps(slim) + "\n")
