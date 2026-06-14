"""
openanalog/forge/sizer.py

Generic numeric sizing search for any registered Topology.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any, Callable

from openanalog.forge.topologies.base import Topology, TopologyMetrics, get_topology
from openanalog.forge.topologies.opamp import OpAmpTopology

# backward compat
MEASURABLE = OpAmpTopology().measurable_specs()


def _satisfaction(metric: float | None, value: float, mode: str) -> float:
    if metric is None:
        return 0.0
    if mode == "min":
        return max(0.0, min(1.0, metric / value)) if value > 0 else 1.0
    if mode == "max":
        if metric <= 0:
            return 1.0
        return max(0.0, min(1.0, value / metric))
    if value == 0:
        return 1.0
    rel = abs(metric - value) / value
    return max(0.0, 1.0 - rel)


def _passes(metric: float | None, value: float, mode: str, tol: float = 0.3) -> bool:
    if metric is None:
        return False
    if mode == "min":
        return metric >= value * 0.98
    if mode == "max":
        return metric <= value * 1.02
    return abs(metric - value) <= value * tol


@dataclass
class Candidate:
    params: Any
    metrics: TopologyMetrics
    score: float
    per_spec: dict[str, dict[str, Any]] = field(default_factory=dict)
    meets_all: bool = False
    topology: str = ""


def score_design(
    metrics: TopologyMetrics,
    targets: dict[str, dict[str, Any]],
    *,
    measurable: set[str] | None = None,
    weights: dict[str, float] | None = None,
    stability_key: str | None = "pm_deg",
    stability_min: float = 30.0,
) -> Candidate:
    measurable = measurable or set(metrics.values.keys())
    weights = weights or {}
    per_spec: dict[str, dict[str, Any]] = {}
    total_w = 0.0
    acc = 0.0
    meets_all = True
    mdict = metrics.as_dict()
    for key, spec in targets.items():
        metric = mdict.get(key)
        value = float(spec["value"])
        mode = spec.get("mode", "target")
        if key not in measurable:
            per_spec[key] = {
                "target": value,
                "mode": mode,
                "measured": None,
                "satisfaction": None,
                "pass": None,
            }
            continue
        sat = _satisfaction(metric, value, mode)
        ok = _passes(metric, value, mode)
        meets_all = meets_all and ok
        w = weights.get(key, 0.5)
        total_w += w
        acc += w * sat
        per_spec[key] = {
            "target": value,
            "mode": mode,
            "measured": metric,
            "satisfaction": round(sat, 3),
            "pass": ok,
        }
    base = acc / total_w if total_w else 0.0
    if stability_key and stability_key in per_spec:
        pm = mdict.get(stability_key)
        if pm is None or pm < stability_min:
            base *= 0.3
    score = base + (0.25 if meets_all else 0.0)
    return Candidate(params=None, metrics=metrics, score=score, per_spec=per_spec, meets_all=meets_all)  # type: ignore


def _sample(
    rng: random.Random,
    ranges: dict[str, tuple[float, float, bool]],
    default: Any,
    *,
    base: Any | None = None,
    jitter: float = 0.0,
) -> Any:
    cls = type(default)
    p = cls()
    cur = base.as_dict() if base else None
    for key, (lo, hi, is_log) in ranges.items():
        if not hasattr(p, key):
            continue
        if cur is not None and jitter > 0:
            center = cur[key]
            if is_log and center > 0:
                lc, hc = math.log(lo), math.log(hi)
                c = math.log(max(center, lo))
                span = (hc - lc) * jitter
                val = math.exp(min(hc, max(lc, rng.uniform(c - span, c + span))))
            else:
                span = (hi - lo) * jitter
                val = min(hi, max(lo, rng.uniform(center - span, center + span)))
        else:
            if is_log and lo > 0:
                val = math.exp(rng.uniform(math.log(lo), math.log(hi)))
            else:
                val = rng.uniform(lo, hi)
        if key == "stages":
            val = int(round(val))
        setattr(p, key, val)
    return p


def size(
    topology: Topology | str,
    spec: dict[str, Any],
    *,
    budget: int = 60,
    seed: int = 0,
    progress: Callable[[int, int, float], None] | None = None,
) -> Candidate:
    """Search device parameters for any topology meeting spec['targets']."""
    if isinstance(topology, str):
        topology = get_topology(topology)
    rng = random.Random(seed)
    targets = spec.get("targets", {})
    supply_V = float(spec.get("supply_V", 5.0))
    cload_F = float(spec.get("cload_F", 10e-12))
    ranges = topology.param_ranges()
    default = topology.default_params()
    measurable = topology.measurable_specs()
    weights = topology.spec_weights
    stability_key = "pm_deg" if "pm_deg" in measurable else None

    pool: list[Candidate] = []
    best: Candidate | None = None
    explore = max(1, int(budget * 0.6))
    topk_n = 5 if topology.circuit_type == "opamp" else 3

    for i in range(budget):
        if best is not None and i >= explore:
            jitter = 0.25 * (1.0 - (i - explore) / max(1, budget - explore))
            p = _sample(rng, ranges, default, base=best.params, jitter=max(0.06, jitter))
        else:
            p = _sample(rng, ranges, default)

        m = topology.measure(p, supply_V=supply_V, cload_F=cload_F, with_full=False)
        extra = topology.estimate_extra(p, cload_F=cload_F)
        for k, v in extra.items():
            if m.values.get(k) is None:
                m.values[k] = v
        cand = score_design(
            m, targets, measurable=measurable, weights=weights, stability_key=stability_key
        )
        cand.params = p
        cand.topology = topology.circuit_type
        pool.append(cand)
        if best is None or cand.score > best.score:
            best = cand
        if progress:
            progress(i + 1, budget, best.score)

    assert best is not None
    pool.sort(key=lambda c: c.score, reverse=True)
    topk = pool[: min(topk_n, len(pool))]
    validated: list[Candidate] = []
    for cand in topk:
        final = topology.measure(cand.params, supply_V=supply_V, cload_F=cload_F, with_full=True)
        out = score_design(
            final, targets, measurable=measurable, weights=weights, stability_key=stability_key
        )
        out.params = cand.params
        out.topology = topology.circuit_type
        validated.append(out)
    validated.sort(key=lambda c: (c.meets_all, c.score), reverse=True)
    return validated[0]


def size_opamp(
    spec: dict[str, Any],
    *,
    budget: int = 60,
    seed: int = 0,
    progress: Callable[[int, int, float], None] | None = None,
) -> Candidate:
    """Backward-compatible op-amp sizing entry point."""
    return size("opamp", spec, budget=budget, seed=seed, progress=progress)
