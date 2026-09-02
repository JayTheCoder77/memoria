from __future__ import annotations

import uuid

from memory_api.db.models import MemoryType
from memory_api.db.repository import InMemoryMemoryRepository
from memory_api.services.consolidation import consolidate_session
from memory_api.services.embedding import HashEmbedder, embed_text


def test_consolidation_merges_near_duplicates_in_a_session() -> None:
    repo = InMemoryMemoryRepository()
    embedder = HashEmbedder()
    org_id = uuid.uuid4()
    vector = embed_text("prefer pytest", embedder=embedder)
    repo.insert(
        org_id=org_id,
        session_id="s1",
        memory_type=MemoryType.semantic,
        content="prefer pytest",
        embedding=vector,
        importance=0.4,
        source_metadata={},
    )
    repo.insert(
        org_id=org_id,
        session_id="s1",
        memory_type=MemoryType.semantic,
        content="we prefer pytest in this repo",
        embedding=list(vector),
        importance=0.7,
        source_metadata={},
    )
    merged = consolidate_session(repo=repo, org_id=org_id, session_id="s1")
    assert merged == 1
    assert len(repo._rows) == 1
    assert repo._rows[0].importance == 0.7
    assert "prefer pytest" in repo._rows[0].content
    assert "we prefer pytest" in repo._rows[0].content
