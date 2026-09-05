from __future__ import annotations

import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_ENRICH_TIMEOUT_SECONDS = 10.0

_LLM_SYSTEM = (
    "Extract structured indexes from one memory. Do not rewrite the memory. "
    'Return JSON {"kv_triples":[{"fact_type":string,"entity":string,'
    '"value":string|null}],"graph_triples":[{"subject":string,"relation":string,'
    '"object":string}]}. Empty arrays are valid. Skip noise.'
)


def _parse_kv_triples(raw: object) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    triples: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        fact_type = str(item.get("fact_type") or "").strip()
        entity = str(item.get("entity") or "").strip()
        if not fact_type or not entity:
            continue
        entry: dict[str, Any] = {"fact_type": fact_type, "entity": entity}
        if item.get("value") is not None:
            entry["value"] = str(item["value"])
        else:
            entry["value"] = None
        triples.append(entry)
    return triples


def _parse_graph_triples(raw: object) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    triples: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        subject = str(item.get("subject") or "").strip()
        relation = str(item.get("relation") or "").strip()
        object_key = str(item.get("object") or "").strip()
        if not subject or not relation or not object_key:
            continue
        triples.append(
            {"subject": subject, "relation": relation, "object": object_key}
        )
    return triples


def _llm_enrich(
    content: str,
    *,
    api_key: str,
    model: str,
    base_url: str,
    http: httpx.Client,
    http_referer: str,
    app_title: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    response = http.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": http_referer,
            "X-Title": app_title,
        },
        json={
            "model": model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": _LLM_SYSTEM},
                {"role": "user", "content": content},
            ],
        },
    )
    response.raise_for_status()
    raw = response.json()["choices"][0]["message"]["content"] or "{}"
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("LLM enrich payload is not an object")
    return _parse_kv_triples(payload.get("kv_triples")), _parse_graph_triples(
        payload.get("graph_triples")
    )


def enrich_hybrid_triples(
    content: str,
    *,
    api_key: str | None = None,
    model: str | None = None,
    http: httpx.Client | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not api_key or not content.strip():
        return [], []

    from memory_api.config import settings

    def _call(client: httpx.Client) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        try:
            return _llm_enrich(
                content,
                api_key=api_key,
                model=model or settings.llm_model,
                base_url=settings.llm_base_url,
                http=client,
                http_referer=settings.openrouter_http_referer,
                app_title=settings.openrouter_app_title,
            )
        except Exception:
            logger.exception("Hybrid triple LLM failed; using rules fallback")
            return [], []

    if http is None:
        with httpx.Client(timeout=_ENRICH_TIMEOUT_SECONDS) as client:
            return _call(client)
    return _call(http)
