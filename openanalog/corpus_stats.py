"""
openanalog/corpus_stats.py

Data-driven achievable spec ranges from the forge winners corpus.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any

from openanalog.config import ROOT
from openanalog.forge.spec_envelopes import DATASHEET_PARTS, DEV_MODE_SPECS

WINNERS_PATH = ROOT / "data" / "training" / "winners.jsonl"

# Metrics highlighted for battery / low-power and current use cases
CURRENT_METRICS = frozenset({"iq_uA", "iout_mA", "dropout_mV"})


def _percentile(sorted_vals: list[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * pct / 100.0
    lo = int(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = k - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def load_winners(path: Path | None = None) -> list[dict[str, Any]]:
    p = path or WINNERS_PATH
    if not p.exists():
        return []
    rows: list[dict[str, Any]] = []
    with p.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def compute_achievable_ranges(
    winners: list[dict[str, Any]] | None = None,
    *,
    path: Path | None = None,
) -> dict[str, Any]:
    """Group winners by topology and compute min/median/max per measured spec."""
    rows = winners if winners is not None else load_winners(path)
    by_topo: dict[str, list[dict[str, float | None]]] = {}
    for w in rows:
        if w.get("fitness") != 1:
            continue
        topo = w.get("topology") or w.get("category") or "unknown"
        specs = w.get("measured_specs") or {}
        by_topo.setdefault(topo, []).append(specs)

    categories: dict[str, Any] = {}
    for topo, spec_list in sorted(by_topo.items()):
        keys: set[str] = set()
        for s in spec_list:
            keys.update(s.keys())
        metrics: dict[str, Any] = {}
        for key in sorted(keys):
            vals = [float(s[key]) for s in spec_list if s.get(key) is not None]
            if not vals:
                continue
            vals.sort()
            metrics[key] = {
                "min": vals[0],
                "max": vals[-1],
                "median": statistics.median(vals),
                "p10": _percentile(vals, 10),
                "p90": _percentile(vals, 90),
                "count": len(vals),
            }
        envelope = DEV_MODE_SPECS.get(topo, "")
        categories[topo] = {
            "winner_count": len(spec_list),
            "part": DATASHEET_PARTS.get(topo, ""),
            "envelope": envelope,
            "metrics": metrics,
            "low_power_note": _low_power_note(topo, metrics),
        }

    return {
        "source": str(path or WINNERS_PATH),
        "total_winners": len(rows),
        "fitness1_count": sum(1 for w in rows if w.get("fitness") == 1),
        "categories": categories,
    }


def _low_power_note(topo: str, metrics: dict[str, Any]) -> str | None:
    iq = metrics.get("iq_uA")
    if not iq:
        return None
    med = iq.get("median")
    if med is None:
        return None
    if topo in ("comparator", "ldo") and med < 1.0:
        return f"Battery-friendly: median Iq {med:.2f} µA"
    if topo == "opamp" and med < 30.0:
        return f"Low-power op-amp: median Iq {med:.1f} µA"
    if topo == "switch" and med < 0.1:
        return f"Ultra-low leakage switch: median Iq {med:.3f} µA"
    if topo == "charge_pump" and med < 100.0:
        return f"Efficient pump: median supply current {med:.1f} µA"
    return None


def achievable_ranges_payload(path: Path | None = None) -> dict[str, Any]:
    return compute_achievable_ranges(path=path)
