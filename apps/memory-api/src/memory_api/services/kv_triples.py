from __future__ import annotations

import re
from typing import Any, TypedDict

from memory_api.config import settings
from memory_api.services.extraction import Candidate
from memory_api.stores.kv import normalize_kv_token

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


class KvTriple(TypedDict):
    fact_type: str
    entity: str
    value: str | None


def _normalize_explicit(triple: dict[str, Any]) -> KvTriple | None:
    fact_type = normalize_kv_token(str(triple.get("fact_type") or ""))
    entity = normalize_kv_token(str(triple.get("entity") or ""))
    if not fact_type or not entity:
        return None
    value = triple.get("value")
    if value is not None:
        value = str(value)
    return {"fact_type": fact_type, "entity": entity, "value": value}


def _heuristic_triples(content: str) -> list[KvTriple]:
    triples: list[KvTriple] = []
    seen: set[tuple[str, str]] = set()

    def add(fact_type: str, entity: str) -> None:
        fact_type_n = normalize_kv_token(fact_type)
        entity_n = normalize_kv_token(entity)
        if not fact_type_n or not entity_n:
            return
        key = (fact_type_n, entity_n)
        if key in seen:
            return
        seen.add(key)
        triples.append({"fact_type": fact_type_n, "entity": entity_n, "value": None})

    for match in _PREFERENCE.finditer(content):
        add("preference", match.group(1))
    for match in _CITY.finditer(content):
        add("city", match.group(1))
    for match in _DECISION.finditer(content):
        add("decision", match.group(1))
    for match in _LANGUAGE.finditer(content):
        add("language", match.group(1))
    return triples


def resolve_kv_triples(candidate: Candidate) -> list[KvTriple]:
    cap = settings.kv_max_triples_per_add
    explicit: list[KvTriple] = []
    for triple in candidate.kv_triples:
        if not isinstance(triple, dict):
            continue
        normalized = _normalize_explicit(triple)
        if normalized is not None:
            explicit.append(normalized)
    if explicit:
        return explicit[:cap]
    return _heuristic_triples(candidate.content)[:cap]
