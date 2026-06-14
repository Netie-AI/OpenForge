"""Topology parameter mutation for forge — seeds inform bounds, not netlist shape."""

from __future__ import annotations

import math
import random
from typing import Any

from openanalog.forge.topologies.base import Topology

WARM_START_FRACTION = 0.35
WARM_JITTER = 0.3

# Smoke-passing opamp params (seed=42, bundled level-1).
OPAMP_WARM_CENTER: dict[str, float] = {
    "W1": 1.975,
    "L1": 1.389,
    "W3": 2.314,
    "L3": 1.0,
    "W5": 6.633,
    "L5": 1.0,
    "W6": 83.25,
    "L6": 1.022,
    "W7": 120.0,
    "L7": 1.0,
    "Wb": 31.37,
    "Lb": 1.0,
    "Iref": 4.74e-6,
    "Cc": 1.9e-12,
}

# Tight bounds around the known-good region for warm-start phase.
OPAMP_WARM_RANGES: dict[str, tuple[float, float, bool]] = {
    "W1": (1.0, 4.0, True),
    "L1": (0.8, 3.0, False),
    "W3": (1.0, 5.0, True),
    "L3": (0.8, 2.0, False),
    "W5": (3.0, 15.0, True),
    "L5": (0.8, 2.0, False),
    "W6": (40.0, 120.0, True),
    "L6": (0.8, 2.0, False),
    "W7": (80.0, 120.0, True),
    "L7": (0.8, 2.0, False),
    "Wb": (15.0, 50.0, True),
    "Lb": (0.8, 2.0, False),
    "Iref": (2e-6, 10e-6, True),
    "Cc": (0.5e-12, 5e-12, True),
}


def opamp_warm_start_params() -> dict[str, float]:
    return dict(OPAMP_WARM_CENTER)


def _clamp(key: str, val: float, lo: float, hi: float) -> float:
    if key == "stages":
        return float(int(round(min(hi, max(lo, val)))))
    if key == "n_phases":
        v = int(round(min(hi, max(lo, val))))
        return 4.0 if v >= 3 else 2.0
    if key == "Cc":
        return max(0.0, min(hi, max(lo, val)))
    if key == "Iref":
        return max(50e-9, min(hi, max(lo, val)))
    if key == "cap_F":
        return max(10e-9, min(hi, max(lo, val)))
    return min(hi, max(lo, val))


def _sample_range(
    rng: random.Random,
    key: str,
    center: float,
    lo: float,
    hi: float,
    is_log: bool,
    jitter: float,
) -> float:
    if is_log and center > 0 and lo > 0:
        lc, hc = math.log(lo), math.log(hi)
        c = math.log(max(center, lo))
        span = (hc - lc) * jitter
        val = math.exp(min(hc, max(lc, rng.uniform(c - span, c + span))))
    else:
        span = (hi - lo) * jitter
        val = rng.uniform(center - span, center + span)
    return _clamp(key, val, lo, hi)


def _mutate_opamp_warm(rng: random.Random) -> dict[str, float]:
    merged = dict(OPAMP_WARM_CENTER)
    for key, (lo, hi, is_log) in OPAMP_WARM_RANGES.items():
        center = OPAMP_WARM_CENTER.get(key, (lo + hi) / 2)
        merged[key] = _sample_range(rng, key, center, lo, hi, is_log, WARM_JITTER)
    return merged


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
    generation: int = 0,
    total: int = 1,
    category: str = "",
) -> Any:
    """Random parameter mutation within topology.param_ranges()."""
    rng = random.Random(seed)
    circuit = category or getattr(topology, "circuit_type", "")

    warm_n = max(1, int(total * WARM_START_FRACTION)) if total > 0 else 0
    if circuit == "opamp" and generation < warm_n:
        return topology.params_from_dict(_mutate_opamp_warm(rng))

    if circuit == "opamp":
        merged = dict(OPAMP_WARM_CENTER)
        ranges = {**topology.param_ranges(), **OPAMP_WARM_RANGES}
        jitter = 0.35
    else:
        merged = params.as_dict()
        ranges = topology.param_ranges()

    for key, (lo, hi, is_log) in ranges.items():
        if key not in merged:
            continue
        center = merged[key]
        merged[key] = _sample_range(rng, key, center, lo, hi, is_log, jitter)
    return topology.params_from_dict(merged)
