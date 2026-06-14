"""Tests for LLM router (offline — no API calls)."""

from openanalog.llm import available_providers, _fallback_chain
from openanalog.interface.datasheet import _looks_like_inline_spec


def test_fallback_chain_prefers_openrouter_by_default():
    chain = _fallback_chain(None)
    assert chain[0] in ("openrouter", "anthropic", "openai", "groq", "sea-lion")


def test_available_providers_structure():
    providers = available_providers()
    assert len(providers) >= 4
    assert all(hasattr(p, "id") and hasattr(p, "available") for p in providers)


def test_inline_spec_detection():
    assert _looks_like_inline_spec("gbp=1.1MHz pm>60 aol>95dB iq<80uA")
    assert not _looks_like_inline_spec("design me a low power comparator")
