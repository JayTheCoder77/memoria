from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import httpx

from memory_api.observability.tracing import start_span
from memory_api.observability.usage import record_llm_usage

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LlmProvider:
    api_key: str
    base_url: str
    model: str
    timeout: float = 10.0
    extra_headers: dict[str, str] = field(default_factory=dict)


def _token_count(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def _usage_tokens(body: object) -> tuple[int, int]:
    if not isinstance(body, dict):
        return 0, 0
    usage = body.get("usage")
    if not isinstance(usage, dict):
        return 0, 0
    return _token_count(usage.get("prompt_tokens")), _token_count(usage.get("completion_tokens"))


def _trace_id(span: Any) -> str | None:
    context = span.get_span_context()
    if not context.is_valid:
        return None
    return format(context.trace_id, "032x")


def complete_json(
    messages: list[dict[str, str]],
    *,
    providers: list[LlmProvider],
    http: httpx.Client | None = None,
    org_id: UUID | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    for provider in providers:
        if not provider.api_key.strip():
            continue
        try:
            with start_span("llm_complete", model=provider.model) as span:
                started = time.perf_counter()
                payload, input_tokens, output_tokens = _one(
                    messages, provider=provider, http=http
                )
                duration_ms = (time.perf_counter() - started) * 1000.0
                trace_id = _trace_id(span)
        except Exception as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            logger.warning(
                "LLM provider %s model %s failed (%s)",
                provider.base_url,
                provider.model,
                status or exc,
            )
            continue
        if org_id is not None:
            try:
                record_llm_usage(
                    org_id=org_id,
                    user_id=user_id,
                    model=provider.model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    duration_ms=duration_ms,
                    trace_id=trace_id,
                )
            except Exception:
                logger.exception("failed to record llm usage for model %s", provider.model)
        if payload:
            return payload
    return {}


def _one(
    messages: list[dict[str, str]],
    *,
    provider: LlmProvider,
    http: httpx.Client | None,
) -> tuple[dict[str, Any], int, int]:
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

    def _parse(response: httpx.Response) -> tuple[dict[str, Any], int, int]:
        response.raise_for_status()
        body = response.json()
        input_tokens, output_tokens = _usage_tokens(body)
        raw = body["choices"][0]["message"]["content"] or "{}"
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            parsed = {}
        return parsed, input_tokens, output_tokens

    if http is None:
        with httpx.Client(timeout=provider.timeout) as client:
            return _parse(client.post(url, headers=headers, json=body))
    return _parse(http.post(url, headers=headers, json=body))
