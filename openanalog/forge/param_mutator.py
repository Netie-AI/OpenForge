"""Topology parameter mutation for forge — seeds inform bounds, not netlist shape."""

from __future__ import annotations

import math
import random
from typing import Any

from openanalog.forge.topologies.base import Topology


def apply_seed_hints(default: Any, hints: dict[str, float], topology: Topology) -> Any:
    """Overlay extracted seed W/L/bias onto topology default params."""
    if not hints:
        return default
    merged = default.as_dict()
    fields = set(merged.keys())
    for key, val in hints.items():
        if key in fields:
            merged[key] = val
            continue
        for cand in (key.lower(), key.upper()):
            if cand in fields:
                merged[cand] = val
                break
    return topology.params_from_dict(merged)


def mutate_params(
    topology: Topology,
    params: Any,
    *,
    seed: int = 0,
    jitter: float = 0.4,
) -> Any:
    """Random parameter mutation within topology.param_ranges()."""
    rng = random.Random(seed)
    ranges = topology.param_ranges()
    merged = params.as_dict()
    for key, (lo, hi, is_log) in ranges.items():
        if key not in merged:
            continue
        center = merged[key]
        if is_log and center > 0 and lo > 0:
            lc, hc = math.log(lo), math.log(hi)
            c = math.log(max(center, lo))
            span = (hc - lc) * jitter
            val = math.exp(min(hc, max(lc, rng.uniform(c - span, c + span))))
        else:
            span = (hi - lo) * jitter
            val = min(hi, max(lo, rng.uniform(center - span, center + span)))
        if key == "stages":
            val = int(round(val))
        if key == "Iref":
            val = max(val, 50e-9)
        if key == "cap_F":
            val = max(val, 10e-9)
        merged[key] = val
    return topology.params_from_dict(merged)
