"""
openanalog/llm.py

Multi-provider LLM router with ordered fallback.
Providers: anthropic, openrouter (GPT via OpenRouter), groq, sea-lion, openai.
"""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openanalog.config import (
    ANTHROPIC_API_KEY,
    GROQ_API_KEY,
    OPENAI_API_KEY,
    OPENFORGE_CLAUDE_MODEL,
    OPENFORGE_GPT_MODEL,
    OPENFORGE_GROQ_MODEL,
    OPENFORGE_LLM_MODEL,
    OPENFORGE_LLM_PROVIDER,
    OPENFORGE_SEA_LION_MODEL,
    OPENROUTER_API_KEY,
    SEA_LION_API_KEY,
)

PROVIDER_DEFAULTS: dict[str, str] = {
    "anthropic": OPENFORGE_CLAUDE_MODEL,
    "openrouter": OPENFORGE_GPT_MODEL,
    "openai": "gpt-4.1",
    "groq": OPENFORGE_GROQ_MODEL,
    "sea-lion": OPENFORGE_SEA_LION_MODEL,
    "sea_lion": OPENFORGE_SEA_LION_MODEL,
}


@dataclass
class ProviderInfo:
    id: str
    label: str
    model: str
    available: bool


def _parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        return json.loads(m.group())
    return json.loads(text)


def available_providers() -> list[ProviderInfo]:
    """Return providers with keys configured."""
    checks = [
        ("openrouter", "OpenRouter (GPT)", OPENROUTER_API_KEY, OPENFORGE_GPT_MODEL),
        ("anthropic", "Anthropic Claude", ANTHROPIC_API_KEY, OPENFORGE_CLAUDE_MODEL),
        ("openai", "OpenAI", OPENAI_API_KEY, "gpt-4.1"),
        ("groq", "Groq", GROQ_API_KEY, OPENFORGE_GROQ_MODEL),
        ("sea-lion", "SEA-LION", SEA_LION_API_KEY, OPENFORGE_SEA_LION_MODEL),
    ]
    return [
        ProviderInfo(id=pid, label=label, model=model, available=bool(key))
        for pid, label, key, model in checks
    ]


def _resolve_model(provider: str, model: str | None) -> str:
    if model:
        return model
    if OPENFORGE_LLM_MODEL and provider == OPENFORGE_LLM_PROVIDER:
        return OPENFORGE_LLM_MODEL
    return PROVIDER_DEFAULTS.get(provider, OPENFORGE_GPT_MODEL)


def _fallback_chain(preferred: str | None) -> list[str]:
    order = ["openrouter", "anthropic", "openai", "groq", "sea-lion"]
    if preferred and preferred in order:
        order.remove(preferred)
        order.insert(0, preferred)
    elif OPENFORGE_LLM_PROVIDER in order:
        order.remove(OPENFORGE_LLM_PROVIDER)
        order.insert(0, OPENFORGE_LLM_PROVIDER)
    return order


def _provider_has_key(provider: str) -> bool:
    return {
        "anthropic": bool(ANTHROPIC_API_KEY),
        "openrouter": bool(OPENROUTER_API_KEY),
        "openai": bool(OPENAI_API_KEY),
        "groq": bool(GROQ_API_KEY),
        "sea-lion": bool(SEA_LION_API_KEY),
        "sea_lion": bool(SEA_LION_API_KEY),
    }.get(provider, False)


def _encode_image(image_path: Path) -> tuple[str, str]:
    media = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
    b64 = base64.standard_b64encode(image_path.read_bytes()).decode()
    return media, b64


def _call_anthropic(system: str, user: str, model: str, image_path: Path | None) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    content: list[dict[str, Any]] = [{"type": "text", "text": user}]
    if image_path and image_path.exists():
        media, b64 = _encode_image(image_path)
        content = [
            {"type": "image", "source": {"type": "base64", "media_type": media, "data": b64}},
            {"type": "text", "text": user},
        ]
    msg = client.messages.create(
        model=model,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": content}],
    )
    return msg.content[0].text


def _call_openai_compat(
    system: str,
    user: str,
    model: str,
    *,
    api_key: str,
    base_url: str | None = None,
    extra_headers: dict[str, str] | None = None,
    image_path: Path | None = None,
) -> str:
    from openai import OpenAI

    kwargs: dict[str, Any] = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    client = OpenAI(**kwargs)
    headers = extra_headers or {}

    if image_path and image_path.exists():
        media, b64 = _encode_image(image_path)
        content: list[dict[str, Any]] = [
            {"type": "text", "text": user},
            {
                "type": "image_url",
                "image_url": {"url": f"data:{media};base64,{b64}"},
            },
        ]
    else:
        content = user

    resp = client.chat.completions.create(
        model=model,
        max_tokens=4096,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": content},
        ],
        extra_headers=headers if headers else None,
    )
    return resp.choices[0].message.content or ""


def ask_text(
    system: str,
    user: str,
    *,
    provider: str | None = None,
    model: str | None = None,
    image_path: Path | None = None,
) -> tuple[str, str, str]:
    """
    Call LLM and return (text, provider_used, model_used).
    Raises RuntimeError if no provider succeeds.
    """
    errors: list[str] = []
    for prov in _fallback_chain(provider):
        if not _provider_has_key(prov):
            continue
        mdl = _resolve_model(prov, model if prov == (provider or prov) else None)
        try:
            if prov == "anthropic":
                text = _call_anthropic(system, user, mdl, image_path)
            elif prov == "openrouter":
                text = _call_openai_compat(
                    system,
                    user,
                    mdl,
                    api_key=OPENROUTER_API_KEY,
                    base_url="https://openrouter.ai/api/v1",
                    extra_headers={
                        "HTTP-Referer": "https://openforge.local",
                        "X-Title": "OpenForge",
                    },
                    image_path=image_path,
                )
            elif prov == "openai":
                text = _call_openai_compat(
                    system, user, mdl, api_key=OPENAI_API_KEY, image_path=image_path
                )
            elif prov == "groq":
                text = _call_openai_compat(
                    system,
                    user,
                    mdl,
                    api_key=GROQ_API_KEY,
                    base_url="https://api.groq.com/openai/v1",
                    image_path=image_path,
                )
            elif prov in ("sea-lion", "sea_lion"):
                text = _call_openai_compat(
                    system,
                    user,
                    mdl,
                    api_key=SEA_LION_API_KEY,
                    base_url="https://api.sea-lion.ai/v1",
                    image_path=image_path,
                )
            else:
                continue
            return text, prov, mdl
        except Exception as e:
            errors.append(f"{prov}/{mdl}: {e}")
    raise RuntimeError("All LLM providers failed: " + "; ".join(errors))


def ask_json(
    system: str,
    user: str,
    *,
    provider: str | None = None,
    model: str | None = None,
    image_path: Path | None = None,
) -> dict[str, Any]:
    text, prov, mdl = ask_text(
        system, user, provider=provider, model=model, image_path=image_path
    )
    result = _parse_json(text)
    result["_llm_provider"] = prov
    result["_llm_model"] = mdl
    return result
