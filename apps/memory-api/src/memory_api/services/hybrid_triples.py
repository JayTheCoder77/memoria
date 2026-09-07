from __future__ import annotations

import logging
from typing import Any

import httpx

from memory_api.services.llm_json import LlmProvider, complete_json

logger = logging.getLogger(__name__)

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


def enrich_hybrid_triples(
    content: str,
    *,
    providers: list[LlmProvider] | None = None,
    http: httpx.Client | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not content.strip() or not providers:
        return [], []

    try:
        payload = complete_json(
            [
                {"role": "system", "content": _LLM_SYSTEM},
                {"role": "user", "content": content},
            ],
            providers=providers,
            http=http,
        )
    except Exception:
        logger.exception("Hybrid triple LLM failed; using rules fallback")
        return [], []

    if not payload:
        return [], []

    return _parse_kv_triples(payload.get("kv_triples")), _parse_graph_triples(
        payload.get("graph_triples")
    )
