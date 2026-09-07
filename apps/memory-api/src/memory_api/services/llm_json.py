from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LlmProvider:
    api_key: str
    base_url: str
    model: str
    timeout: float = 10.0
    extra_headers: dict[str, str] = field(default_factory=dict)


def complete_json(
    messages: list[dict[str, str]],
    *,
    providers: list[LlmProvider],
    http: httpx.Client | None = None,
) -> dict[str, Any]:
    for provider in providers:
        if not provider.api_key.strip():
            continue
        try:
            payload = _one(messages, provider=provider, http=http)
        except Exception as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            logger.warning(
                "LLM provider %s model %s failed (%s)",
                provider.base_url,
                provider.model,
                status or exc,
            )
            continue
        if payload:
            return payload
    return {}


def _one(
    messages: list[dict[str, str]],
    *,
    provider: LlmProvider,
    http: httpx.Client | None,
) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {provider.api_key}",
        "Content-Type": "application/json",
        **provider.extra_headers,
    }
    url = f"{provider.base_url.rstrip('/')}/chat/completions"
    body = {
        "model": provider.model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": messages,
    }

    def _parse(response: httpx.Response) -> dict[str, Any]:
        response.raise_for_status()
        raw = response.json()["choices"][0]["message"]["content"] or "{}"
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return {}
        return parsed

    if http is None:
        with httpx.Client(timeout=provider.timeout) as client:
            return _parse(client.post(url, headers=headers, json=body))
    return _parse(http.post(url, headers=headers, json=body))
