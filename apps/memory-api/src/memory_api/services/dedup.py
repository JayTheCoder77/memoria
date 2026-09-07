from __future__ import annotations

import re
import uuid

from memory_api.db.models import Memory
from memory_api.db.repository import MemoryRepository
from memory_api.services.embedding import Embedder, embed_text
from memory_api.services.extraction import Candidate
from memory_api.stores.graph import normalize_graph_token
from memory_api.stores.kv import normalize_kv_token

DEDUP_THRESHOLD = 0.92
ENTITY_OVERLAP_THRESHOLD = 0.80
_WORD = re.compile(r"[a-zA-Z0-9_]+")


def _candidate_entities(candidate: Candidate) -> set[str]:
    tokens: set[str] = set()
    for triple in candidate.kv_triples:
        entity = normalize_kv_token(str(triple.get("entity") or ""))
        if entity:
            tokens.add(entity)
    for triple in candidate.graph_triples:
        for key in ("subject", "object"):
            entity = normalize_graph_token(str(triple.get(key) or ""))
            if entity:
                tokens.add(entity)
    return tokens


def _neighbor_tokens(content: str) -> set[str]:
    return {
        normalize_kv_token(word) for word in _WORD.findall(content) if len(word) >= 2
    }


def _shares_entity(candidate: Candidate, neighbor: Memory) -> bool:
    entities = _candidate_entities(candidate)
    if not entities:
        return False
    tokens = _neighbor_tokens(neighbor.content)
    haystack = neighbor.content.lower()
    for entity in entities:
        if entity in tokens:
            return True
        if len(entity) >= 3 and entity in haystack:
            return True
    return False


def _should_merge(
    similarity: float,
    candidate: Candidate,
    neighbor: Memory,
    *,
    threshold: float,
    overlap_threshold: float = ENTITY_OVERLAP_THRESHOLD,
) -> bool:
    if similarity >= threshold:
        return True
    return similarity >= overlap_threshold and _shares_entity(candidate, neighbor)


def persist_candidate(
    *,
    repo: MemoryRepository,
    embedder: Embedder,
    org_id: uuid.UUID,
    session_id: str,
    candidate: Candidate,
    threshold: float = DEDUP_THRESHOLD,
) -> tuple[Memory, bool]:
    embedding = embed_text(candidate.content, embedder=embedder)
    matches = repo.similar(
        org_id=org_id,
        query_embedding=embedding,
        session_id=session_id,
        limit=1,
    )
    if matches:
        memory, similarity = matches[0]
        if _should_merge(similarity, candidate, memory, threshold=threshold):
            memory.importance = min(1.0, memory.importance + 0.05)
            memory.access_count += 1
            return memory, False
    memory = repo.insert(
        org_id=org_id,
        session_id=session_id,
        memory_type=candidate.memory_type,
        content=candidate.content,
        embedding=embedding,
        importance=candidate.importance,
        source_metadata=candidate.source_metadata,
    )
    return memory, True
