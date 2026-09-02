from __future__ import annotations

import uuid

from memory_api.db.models import MemoryType
from memory_api.db.repository import InMemoryMemoryRepository
from memory_api.services.embedding import HashEmbedder, embed_text


def test_in_memory_search_is_scoped_to_org() -> None:
    repo = InMemoryMemoryRepository()
    embedder = HashEmbedder()
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()
    content = "prefer explicit org_id on every query"
    embedding = embed_text(content, embedder=embedder)

    kept = repo.insert(
        org_id=org_a,
        session_id="s1",
        memory_type=MemoryType.semantic,
        content=content,
        embedding=embedding,
        importance=0.5,
        source_metadata={},
    )
    repo.insert(
        org_id=org_b,
        session_id="s1",
        memory_type=MemoryType.semantic,
        content=content,
        embedding=embedding,
        importance=0.5,
        source_metadata={},
    )

    hits = repo.search(org_id=org_a, query_embedding=embedding, session_id="s1")
    assert [memory.id for memory, _score in hits] == [kept.id]
