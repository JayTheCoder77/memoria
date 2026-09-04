from __future__ import annotations

import json
import logging
import re

import httpx

from memory_api.stores.graph import normalize_graph_token

logger = logging.getLogger(__name__)

_TOKEN = re.compile(r"[a-z0-9]{3,}")
_CAP = 12

_LIVES_IN = re.compile(r"\blives in\s+(\w+)", re.IGNORECASE)
_PREFER = re.compile(r"\bprefer\s+(\w+)", re.IGNORECASE)
_WORKS_ON = re.compile(r"\bworks on\s+(\w+)", re.IGNORECASE)

_LLM_SYSTEM = (
    "Extract entity keys for graph traversal from the user query. "
    'Return JSON {"entities":[string,...]}. '
    "Return entity keys only, not new memories."
)


def _add_seed(results: list[str], seen: set[str], entity: str) -> None:
    if len(results) >= _CAP:
        return
    normalized = normalize_graph_token(entity)
    if not normalized or normalized in seen:
        return
    seen.add(normalized)
    results.append(normalized)


def _rules_seeds(query: str) -> list[str]:
    results: list[str] = []
    seen: set[str] = set()

    for pattern in (_LIVES_IN, _PREFER, _WORKS_ON):
        for match in pattern.finditer(query):
            _add_seed(results, seen, match.group(1))

    for token in _TOKEN.findall(query.lower()):
        _add_seed(results, seen, token)
        if len(results) >= _CAP:
            break

    return results


def _llm_seeds(
    query: str,
    *,
    api_key: str,
    model: str,
    base_url: str,
    http: httpx.Client,
    http_referer: str,
    app_title: str,
) -> list[str]:
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
                {"role": "user", "content": query},
            ],
        },
    )
    response.raise_for_status()
    raw = response.json()["choices"][0]["message"]["content"] or "{}"
    payload = json.loads(raw)
    entities = payload.get("entities")
    if entities is None:
        entities = []
    elif not isinstance(entities, list):
        raise ValueError("LLM entities payload is not a list")
    results: list[str] = []
    seen: set[str] = set()
    for item in entities:
        _add_seed(results, seen, str(item))
        if len(results) >= _CAP:
            break
    return results


def derive_graph_seeds(
    query: str,
    *,
    api_key: str | None = None,
    model: str | None = None,
    http_client: httpx.Client | None = None,
) -> list[str]:
    if not api_key:
        return _rules_seeds(query)

    from memory_api.config import settings

    def _derive_with_llm(client: httpx.Client) -> list[str]:
        try:
            return _llm_seeds(
                query,
                api_key=api_key,
                model=model or settings.llm_model,
                base_url=settings.llm_base_url,
                http=client,
                http_referer=settings.openrouter_http_referer,
                app_title=settings.openrouter_app_title,
            )
        except Exception:
            logger.exception("Graph seed LLM failed; using rules fallback")
            return _rules_seeds(query)

    if http_client is None:
        with httpx.Client(timeout=30.0) as client:
            return _derive_with_llm(client)
    return _derive_with_llm(http_client)
