from __future__ import annotations

import re
from typing import Any, TypedDict

from memory_api.config import settings
from memory_api.services.extraction import Candidate
from memory_api.stores.graph import normalize_graph_token

_LIVES_IN = re.compile(r"\b(?:lives in|moved to)\s+(\S+)", re.IGNORECASE)
_PREFERS = re.compile(r"\b(?:prefer|prefers)\s+(\S+)", re.IGNORECASE)
_WORKS_ON = re.compile(r"\bworks on\s+(\S+)", re.IGNORECASE)


class GraphTriple(TypedDict, total=False):
    subject: str
    relation: str
    object: str
    confidence: float


def _normalize_explicit(triple: dict[str, Any]) -> GraphTriple | None:
    subject = normalize_graph_token(str(triple.get("subject") or ""))
    relation = normalize_graph_token(str(triple.get("relation") or ""))
    object_key = normalize_graph_token(str(triple.get("object") or ""))
    if not subject or not relation or not object_key:
        return None
    result: GraphTriple = {"subject": subject, "relation": relation, "object": object_key}
    if triple.get("confidence") is not None:
        result["confidence"] = float(triple["confidence"])
    return result


def _strip_token(value: str) -> str:
    return re.sub(r"[^\w-]+$", "", value.strip())


def _heuristic_triples(content: str) -> list[GraphTriple]:
    triples: list[GraphTriple] = []
    seen: set[tuple[str, str, str]] = set()

    def add(relation: str, object_key: str) -> None:
        relation_n = normalize_graph_token(relation)
        object_n = normalize_graph_token(_strip_token(object_key))
        if not relation_n or not object_n:
            return
        key = ("user", relation_n, object_n)
        if key in seen:
            return
        seen.add(key)
        triples.append({"subject": "user", "relation": relation_n, "object": object_n})

    for match in _LIVES_IN.finditer(content):
        add("lives_in", match.group(1))
    for match in _PREFERS.finditer(content):
        add("prefers", match.group(1))
    for match in _WORKS_ON.finditer(content):
        add("works_on", match.group(1))
    return triples


def resolve_graph_triples(candidate: Candidate) -> list[GraphTriple]:
    cap = settings.graph_max_edges_per_add
    explicit: list[GraphTriple] = []
    for triple in candidate.graph_triples:
        if not isinstance(triple, dict):
            continue
        normalized = _normalize_explicit(triple)
        if normalized is not None:
            explicit.append(normalized)
    if explicit:
        return explicit[:cap]
    return _heuristic_triples(candidate.content)[:cap]
