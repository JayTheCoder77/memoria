from __future__ import annotations

import uuid

from memory_api.db.models import MemoryType
from memory_api.db.repository import InMemoryMemoryRepository
from memory_api.services.dedup import persist_candidate
from memory_api.services.embedding import HashEmbedder, embed_text
from memory_api.services.extraction import Candidate


def test_duplicate_content_reinforces_instead_of_inserting() -> None:
    repo = InMemoryMemoryRepository()
    embedder = HashEmbedder()
    org_id = uuid.uuid4()
    candidate = Candidate(
        content="We prefer pytest over unittest.",
        memory_type=MemoryType.semantic,
        importance=0.5,
    )
    first, inserted = persist_candidate(
        repo=repo,
        embedder=embedder,
        org_id=org_id,
        session_id="s1",
        candidate=candidate,
    )
    second, inserted_again = persist_candidate(
        repo=repo,
        embedder=embedder,
        org_id=org_id,
        session_id="s1",
        candidate=candidate,
    )
    assert inserted is True
    assert inserted_again is False
    assert first.id == second.id
    assert len(repo._rows) == 1
    assert second.access_count == 1
    assert second.importance > 0.5


def test_dedup_lookup_does_not_count_as_recall() -> None:
    repo = InMemoryMemoryRepository()
    embedder = HashEmbedder()
    org_id = uuid.uuid4()
    candidate = Candidate(content="unique fact", memory_type=MemoryType.semantic)
    persist_candidate(
        repo=repo,
        embedder=embedder,
        org_id=org_id,
        session_id="s1",
        candidate=candidate,
    )
    similar = repo.similar(
        org_id=org_id,
        query_embedding=embed_text("unique fact", embedder=embedder),
        session_id="s1",
        limit=1,
    )
    assert similar[0][0].access_count == 0
