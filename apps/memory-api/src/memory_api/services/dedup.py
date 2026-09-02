from __future__ import annotations

import uuid

from memory_api.db.models import Memory
from memory_api.db.repository import MemoryRepository
from memory_api.services.embedding import Embedder, embed_text
from memory_api.services.extraction import Candidate

DEDUP_THRESHOLD = 0.92


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
        if similarity >= threshold:
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
