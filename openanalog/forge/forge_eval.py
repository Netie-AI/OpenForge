"""Forge fitness evaluation against RS-series spec envelopes."""

from __future__ import annotations

import logging
from typing import Any

from openanalog.forge.netlist_measure import measure_bench_netlist
from openanalog.forge.sizer import score_design
from openanalog.forge.spec_envelopes import DEV_MODE_SPECS
from openanalog.forge.topologies import get_topology
from openanalog.forge.topology_detector import bench_topologies, resolve_forge_topology
from openanalog.interface.datasheet import parse_inline_spec
from openanalog.sim.ngspice import check_syntax
from openanalog.ingestion.converter import prepare_seed_deck

_log = logging.getLogger(__name__)

_UNSCORED_LOGGED = 0


def _score_topology_metrics(
    category: str,
    metrics,
    *,
    topology=None,
) -> dict[str, Any]:
    if topology is None:
        topology = get_topology(category)
    spec = parse_inline_spec(DEV_MODE_SPECS[category], category=category)
    cand = score_design(
        metrics,
        spec["targets"],
        measurable=topology.measurable_specs(),
        weights=topology.spec_weights,
    )
    failed = [k for k, v in cand.per_spec.items() if v.get("pass") is False]
    score = 1 if cand.meets_all and metrics.ok else 0
    margins = {
        k: (v.get("measured") if v.get("measured") is not None else -1e9)
        for k, v in cand.per_spec.items()
    }
    return {
        "score": score,
        "failed_checks": failed,
        "margin_per_check": margins,
        "measured": metrics.as_dict(),
        "per_spec": cand.per_spec,
        "sim_ok": metrics.ok,
        "reason": "meets_all" if score else "spec_miss",
    }


def evaluate_topology_params(category: str, params: Any) -> dict[str, Any]:
    """Score sized topology parameters on the RS-series bar."""
    topology = get_topology(category)
    metrics = topology.measure(params, with_full=True)
    out = _score_topology_metrics(category, metrics, topology=topology)
    out["inferred_topology"] = category
    return out


def evaluate_forge_fitness(
    netlist: str,
    seed_circuit_type: str | None = None,
) -> dict[str, Any]:
    """
    Score a mutated seed netlist on the RS-series bar.

    fitness=1 only when measured specs meet ``spec_envelopes.DEV_MODE_SPECS``.
    Unknown / unbenchable topologies always score 0 (no sim_ok shortcut).
    """
    global _UNSCORED_LOGGED
    inferred = resolve_forge_topology(netlist, seed_circuit_type)

    if inferred not in bench_topologies():
        if _UNSCORED_LOGGED < 5:
            _log.info("forge_eval: unbenchable topology=%s seed=%s", inferred, seed_circuit_type)
            _UNSCORED_LOGGED += 1
        return {
            "score": 0,
            "inferred_topology": inferred,
            "failed_checks": ["no_bench_topology"],
            "margin_per_check": {},
            "measured": {},
            "per_spec": {},
            "sim_ok": False,
            "reason": "topology not in bench registry",
        }

    deck = prepare_seed_deck(netlist)
    sim_ok, _ = check_syntax(deck, timeout=8)
    if not sim_ok:
        return {
            "score": 0,
            "inferred_topology": inferred,
            "failed_checks": ["dc_op"],
            "margin_per_check": {},
            "measured": {},
            "per_spec": {},
            "sim_ok": False,
            "reason": "DC operating point failed",
        }

    metrics = measure_bench_netlist(inferred, netlist)
    out = _score_topology_metrics(inferred, metrics)
    out["inferred_topology"] = inferred
    out["sim_ok"] = sim_ok and metrics.ok
    return out
