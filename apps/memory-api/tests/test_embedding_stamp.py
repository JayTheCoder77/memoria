from __future__ import annotations

import uuid

from memory_api.db.models import Memory, MemoryType
from memory_api.db.repository import InMemoryMemoryRepository, search_statement
from memory_api.services.dedup import persist_candidate
from memory_api.services.embedding import (
    EMBEDDING_DIM,
    HashEmbedder,
    HuggingFaceEmbedder,
    MiniLMEmbedder,
)
from memory_api.services.extraction import Candidate


def test_search_returns_only_rows_for_the_requested_embedding_model() -> None:
    repo = InMemoryMemoryRepository()
    org_id = uuid.uuid4()
    embedder = HashEmbedder()
    vector = embedder.embed("shared vector")
    minilm = repo.insert(
        org_id=org_id,
        session_id="s1",
        memory_type=MemoryType.semantic,
        content="minilm memory",
        embedding=vector,
        importance=0.5,
        source_metadata={},
        embedding_model="minilm",
    )
    repo.insert(
        org_id=org_id,
        session_id="s1",
        memory_type=MemoryType.semantic,
        content="hash memory",
        embedding=vector,
        importance=0.5,
        source_metadata={},
        embedding_model="hash",
    )

    hits = repo.search(
        org_id=org_id,
        query_embedding=vector,
        session_id="s1",
        embedding_model="minilm",
    )
    assert [memory.id for memory, _score in hits] == [minilm.id]


def test_persist_candidate_stamps_embedder_model_name() -> None:
    repo = InMemoryMemoryRepository()
    embedder = HashEmbedder()
    memory, inserted = persist_candidate(
        repo=repo,
        embedder=embedder,
        org_id=uuid.uuid4(),
        session_id="s1",
        candidate=Candidate(content="stamp me", memory_type=MemoryType.semantic),
    )
    assert inserted is True
    assert embedder.model_name == "hash"
    assert memory.embedding_model == "hash"
    assert memory.embedding_version == 1


def test_embedder_model_names() -> None:
    assert HashEmbedder().model_name == "hash"
    assert MiniLMEmbedder().model_name == "minilm"
    embedder = HuggingFaceEmbedder(
        token="hf_test",
        model="sentence-transformers/all-MiniLM-L6-v2",
    )
    assert embedder.model_name == "sentence-transformers/all-MiniLM-L6-v2"


def test_search_statement_filters_by_embedding_model() -> None:
    org_id = uuid.uuid4()
    stmt = search_statement(
        org_id=org_id,
        query_embedding=[0.0] * EMBEDDING_DIM,
        embedding_model="minilm",
    )
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": False}))
    assert "memories.embedding_model" in compiled
    assert "minilm" in stmt.compile().params.values()


class _TargetEmbedder(HashEmbedder):
    model_name = "minilm"


def test_reembed_updates_embedding_and_version() -> None:
    from memory_api.cli import rewrite_memory_embedding

    content = "prefer pytest"
    memory = Memory(
        org_id=uuid.uuid4(),
        session_id="s1",
        memory_type=MemoryType.semantic,
        content=content,
        embedding=[0.0] * EMBEDDING_DIM,
        importance=0.5,
        source_metadata={},
        embedding_model="hash",
        embedding_version=1,
    )
    embedder = _TargetEmbedder()
    rewrite_memory_embedding(memory, embedder)
    assert memory.embedding_model == "minilm"
    assert memory.embedding_version == 2
    assert list(memory.embedding) == embedder.embed(content)


def test_reembed_query_is_scoped_to_org() -> None:
    from memory_api.cli import reembed_statement

    org_id = uuid.uuid4()
    other_org = uuid.uuid4()
    stmt = reembed_statement(org_id=org_id, from_model="hash")
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": False}))
    assert "memories.org_id" in compiled
    assert "memories.embedding_model" in compiled
    params = stmt.compile().params
    assert org_id in params.values()
    assert other_org not in params.values()
    assert "hash" in params.values()
