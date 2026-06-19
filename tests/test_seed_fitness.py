"""Tests for Phase 2 seed → forge fitness wiring."""

from __future__ import annotations

import json
from unittest.mock import patch

from openanalog.forge.seed_scoring import (
    corpus_report,
    load_normalized_seeds,
    map_seed_category,
    run_seed_scoring,
    score_seed_record,
    select_benchable_seeds,
)

SIMPLE_RC = """
R1 in out 10k
C1 out 0 1p
V1 in 0 DC 1
.end
"""

OPAMPISH = """
M1 d1 vin tail 0 nmos W=10u L=1u
M2 d2 vinp tail 0 nmos W=10u L=1u
M3 d1 d1 vdd vdd pmos W=20u L=1u
M4 d2 d1 vdd vdd pmos W=20u L=1u
M5 vout d2 0 0 nmos W=30u L=1u
Cc vout d2 1p
VDD vdd 0 DC 3.3
VSS tail 0 DC 0.9
Vin vin 0 DC 1.65
Vinp vinp 0 DC 1.65
.end
"""


def test_map_seed_category_aliases():
    assert map_seed_category("amplifier") == "opamp"
    assert map_seed_category("analog_switch") == "switch"
    assert map_seed_category("unknown_type") is None


def test_score_seed_record_unknown_topology_scores_zero():
    rec = {"id": "t1", "circuit_type": "unknown", "netlist": SIMPLE_RC}
    with patch("openanalog.forge.seed_scoring.evaluate_forge_fitness") as ev:
        ev.return_value = {
            "score": 0,
            "inferred_topology": "unknown",
            "failed_checks": ["no_bench_topology"],
            "margin_per_check": {},
            "measured": {},
            "per_spec": {},
            "sim_ok": False,
        }
        result = score_seed_record(rec)
    assert result is not None
    assert result["won"] is False
    assert result["fit"]["score"] == 0
    ev.assert_called_once()


def test_select_benchable_seeds_prefers_inferred():
    seeds = [
        {"id": "a", "netlist": SIMPLE_RC, "circuit_type": "unknown"},
        {"id": "b", "netlist": OPAMPISH, "circuit_type": "unknown"},
    ]
    picked = select_benchable_seeds(seeds)
    assert len(picked) == 1
    assert picked[0]["id"] == "b"


def test_run_seed_scoring_invokes_callback():
    rec = {"id": "s0", "circuit_type": "opamp", "netlist": OPAMPISH}
    seen: list[str] = []

    def _cb(result, *, generation: int) -> None:
        seen.append(result["seed_id"])

    with patch("openanalog.forge.seed_scoring.load_normalized_seeds", return_value=[rec]):
        with patch("openanalog.forge.seed_scoring.score_seed_record") as score:
            score.return_value = {
                "topo": "opamp",
                "seed_topo": "opamp",
                "seed_id": "s0",
                "child": OPAMPISH,
                "params": {},
                "sim": {},
                "fit": {"score": 0, "failed_checks": [], "margin_per_check": {}},
                "per_spec": {},
                "won": False,
                "sim_ok": True,
                "compliance": {},
            }
            counts = run_seed_scoring(limit=1, process_result=_cb)
    assert counts["scored"] == 1
    assert seen == ["s0"]


def test_corpus_report_missing_file():
    with patch("openanalog.forge.seed_scoring.SEEDS_NORMALIZED") as path:
        path.exists.return_value = False
        report = corpus_report()
    assert report["exists"] is False


def test_load_normalized_seeds_filters_sim_validated(tmp_path, monkeypatch):
    seed_file = tmp_path / "seeds_normalized.jsonl"
    rows = [
        {"id": "1", "sim_validated": True, "netlist": "R1 a b 1k", "circuit_type": "unknown"},
        {"id": "2", "sim_validated": False, "netlist": "R2 a b 2k", "circuit_type": "unknown"},
    ]
    seed_file.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    monkeypatch.setattr("openanalog.forge.seed_scoring.SEEDS_NORMALIZED", seed_file)
    loaded = load_normalized_seeds(sim_validated_only=True)
    assert len(loaded) == 1
    assert loaded[0]["id"] == "1"
