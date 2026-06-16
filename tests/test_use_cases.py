"""Tests for application use-case cards."""

from openanalog.use_cases import USE_CASES, use_cases_payload


def test_use_cases_payload():
    payload = use_cases_payload()
    assert len(payload["use_cases"]) >= 5
    ids = {u["id"] for u in payload["use_cases"]}
    assert "battery_low_iq" in ids
    assert "analog_multiply" in ids
    assert "vector_mac" in ids


def test_use_case_has_products():
    battery = next(u for u in USE_CASES if u.id == "battery_low_iq")
    assert "comparator" in battery.product_ids
    assert "iq_uA" in battery.highlight_metrics
