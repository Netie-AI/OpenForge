"""Tests for corpus-driven achievable ranges."""

from openanalog.corpus_stats import achievable_ranges_payload, compute_achievable_ranges


def test_achievable_ranges_structure():
    payload = achievable_ranges_payload()
    assert "categories" in payload
    assert "total_winners" in payload
    if payload["fitness1_count"] > 0:
        assert len(payload["categories"]) >= 1
        for topo, cat in payload["categories"].items():
            assert cat["winner_count"] > 0
            assert "metrics" in cat


def test_compute_ranges_from_empty():
    out = compute_achievable_ranges([])
    assert out["fitness1_count"] == 0
    assert out["categories"] == {}
