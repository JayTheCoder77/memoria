from __future__ import annotations

import re

from memory_api.stores.kv import normalize_kv_token

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


def derive_kv_candidates(query: str) -> list[tuple[str, str]]:
    return _rules_candidates(query)
