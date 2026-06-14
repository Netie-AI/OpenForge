"""Tests for RS-series forge fitness gate."""

from openanalog.forge.forge_eval import evaluate_forge_fitness

SIMPLE_RC = """
R1 in out 10k
C1 out 0 1p
V1 in 0 DC 1
"""


def test_unknown_topology_scores_zero():
    ev = evaluate_forge_fitness(SIMPLE_RC, "unknown")
    assert ev["score"] == 0
    assert "no_bench_topology" in ev["failed_checks"]


def test_amplifier_label_without_bench_still_zero():
    ev = evaluate_forge_fitness(SIMPLE_RC, "amplifier")
    assert ev["score"] == 0
