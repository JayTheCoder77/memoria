from __future__ import annotations

import json
import logging
import re

import httpx

from memory_api.stores.kv import normalize_kv_token

logger = logging.getLogger(__name__)

_TOKEN = re.compile(r"[a-z0-9]{3,}")
_SEED_TYPES = ("preference", "city", "decision", "language")
_CAP = 12

_PREFERENCE = re.compile(
    r"\b(?:prefer|always|never|we use)\s+(\w+)",
    re.IGNORECASE,
)
_CITY = re.compile(r"\b(?:lives in|in)\s+([A-Z][a-z]+)\b")
_DECISION = re.compile(
    r"\b(?:decided|decision|going with)\s+(\w+)",
    re.IGNORECASE,
)
_LANGUAGE = re.compile(r"\blanguage\s+(\w+)", re.IGNORECASE)

_LLM_SYSTEM = (
    "Extract candidate lookup keys for the user query. "
    'Return JSON {"keys":[{"fact_type":string,"entity":string}, ...]}. '
    "Return lookup keys only, not new memories."
)


def _add_candidate(
    results: list[tuple[str, str]],
    seen: set[tuple[str, str]],
    fact_type: str,
    entity: str,
) -> None:
    if len(results) >= _CAP:
        return
    fact_type_n = normalize_kv_token(fact_type)
    entity_n = normalize_kv_token(entity)
    if not fact_type_n or not entity_n:
        return
    key = (fact_type_n, entity_n)
    if key in seen:
        return
    seen.add(key)
    results.append(key)


def _rules_candidates(query: str) -> list[tuple[str, str]]:
    results: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for match in _PREFERENCE.finditer(query):
        _add_candidate(results, seen, "preference", match.group(1))
    for match in _CITY.finditer(query):
        _add_candidate(results, seen, "city", match.group(1))
    for match in _DECISION.finditer(query):
        _add_candidate(results, seen, "decision", match.group(1))
    for match in _LANGUAGE.finditer(query):
        _add_candidate(results, seen, "language", match.group(1))

    tokens = _TOKEN.findall(query.lower())
    for seed_type in _SEED_TYPES:
        for token in tokens:
            _add_candidate(results, seen, seed_type, token)
            if len(results) >= _CAP:
                return results

    return results


def _llm_candidates(
    query: str,
    *,
    api_key: str,
    model: str,
    base_url: str,
    http: httpx.Client,
    http_referer: str,
    app_title: str,
) -> list[tuple[str, str]]:
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
    results: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in payload.get("keys") or []:
        if not isinstance(item, dict):
            continue
        _add_candidate(
            results,
            seen,
            str(item.get("fact_type") or ""),
            str(item.get("entity") or ""),
        )
        if len(results) >= _CAP:
            break
    return results


def derive_kv_candidates(
    query: str,
    *,
    api_key: str | None = None,
    model: str | None = None,
    http: httpx.Client | None = None,
) -> list[tuple[str, str]]:
    if not api_key:
        return _rules_candidates(query)

    from memory_api.config import settings

    client = http or httpx.Client(timeout=30.0)
    try:
        return _llm_candidates(
            query,
            api_key=api_key,
            model=model or settings.llm_model,
            base_url=settings.llm_base_url,
            http=client,
            http_referer=settings.openrouter_http_referer,
            app_title=settings.openrouter_app_title,
        )
    except Exception:
        logger.exception("KV candidate LLM failed; using rules fallback")
        return _rules_candidates(query)
