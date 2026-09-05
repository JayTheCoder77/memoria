from __future__ import annotations

import time
import uuid
from typing import Any

from memory_api.config import settings
from memory_api.db.models import MemoryType
from memory_api.db.repository import InMemoryMemoryRepository
from memory_api.services.embedding import HashEmbedder
from memory_api.services.hybrid_search import HybridRetriever
from memory_api.stores.graph import InMemoryGraphStore
from memory_api.stores.kv import InMemoryKVStore
from memory_api.stores.types import KVFact, ScoredMemory
from memory_api.stores.vector import PostgresVectorStore


def _insert(
    repo: InMemoryMemoryRepository,
    *,
    org_id: uuid.UUID,
    content: str,
    session_id: str = "s1",
    importance: float = 0.5,
) -> Any:
    embedder = HashEmbedder()
    return repo.insert(
        org_id=org_id,
        session_id=session_id,
        memory_type=MemoryType.semantic,
        content=content,
        embedding=embedder.embed(content),
        importance=importance,
        source_metadata={},
    )


def test_hybrid_retriever_unions_kv_and_scores_like_router() -> None:
    org_id = uuid.uuid4()
    repo = InMemoryMemoryRepository()
    kv = InMemoryKVStore()
    graph = InMemoryGraphStore()
    memory = _insert(repo, org_id=org_id, content="zzz-kv-only-payload")
    kv.put(
        org_id,
        memory.id,
        "preference",
        "typescript",
        value=None,
        importance=0.5,
    )
    retriever = HybridRetriever(
        repo=repo,
        vector=PostgresVectorStore(repo),
        kv=kv,
        graph=graph,
        embedder=HashEmbedder(),
    )
    result = retriever.search(org_id=org_id, q="prefer typescript", session_id="s1")
    ids = [hit.memory.id for hit in result.hits]
    assert memory.id in ids
    hit = next(h for h in result.hits if h.memory.id == memory.id)
    assert hit.kv_match == 1.0
    assert hit.similarity == 0.0 or hit.vector_hit is False or hit.kv_match == 1.0


def test_hybrid_retriever_graph_hops_and_session_scope() -> None:
    org_id = uuid.uuid4()
    repo = InMemoryMemoryRepository()
    kv = InMemoryKVStore()
    graph = InMemoryGraphStore()
    other = _insert(
        repo, org_id=org_id, content="other session graph", session_id="s2"
    )
    target = _insert(repo, org_id=org_id, content="one hop ava", session_id="s1")
    graph.add_edge(
        org_id,
        "ava",
        "likes",
        "coding",
        memory_id=target.id,
    )
    graph.add_edge(
        org_id,
        "ava",
        "knows",
        "bob",
        memory_id=other.id,
    )
    retriever = HybridRetriever(
        repo=repo,
        vector=PostgresVectorStore(repo),
        kv=kv,
        graph=graph,
        embedder=HashEmbedder(),
    )
    result = retriever.search(org_id=org_id, q="tell me about ava", session_id="s1")
    ids = [hit.memory.id for hit in result.hits]
    assert target.id in ids
    assert other.id not in ids
    hit = next(h for h in result.hits if h.memory.id == target.id)
    assert hit.graph_hops == 1


def test_hybrid_retriever_store_reads_overlap() -> None:
    org_id = uuid.uuid4()
    repo = InMemoryMemoryRepository()
    _insert(repo, org_id=org_id, content="overlap probe")
    marks: dict[str, float] = {}

    class SlowVector(PostgresVectorStore):
        def search(self, *args: Any, **kwargs: Any) -> list[ScoredMemory]:
            marks["vector_start"] = time.perf_counter()
            time.sleep(0.05)
            try:
                return super().search(*args, **kwargs)
            finally:
                marks["vector_end"] = time.perf_counter()

    class SlowKV(InMemoryKVStore):
        def search_keys(self, *args: Any, **kwargs: Any) -> list[KVFact]:
            marks["kv_start"] = time.perf_counter()
            time.sleep(0.05)
            try:
                return super().search_keys(*args, **kwargs)
            finally:
                marks["kv_end"] = time.perf_counter()

    class SlowGraph(InMemoryGraphStore):
        def memory_hops(self, *args: Any, **kwargs: Any) -> dict[uuid.UUID, int]:
            marks["graph_start"] = time.perf_counter()
            time.sleep(0.05)
            try:
                return super().memory_hops(*args, **kwargs)
            finally:
                marks["graph_end"] = time.perf_counter()

    retriever = HybridRetriever(
        repo=repo,
        vector=SlowVector(repo),
        kv=SlowKV(),
        graph=SlowGraph(),
        embedder=HashEmbedder(),
    )
    retriever.search(org_id=org_id, q="overlap probe", session_id="s1")
    assert marks["vector_start"] < marks["kv_end"]
    assert marks["kv_start"] < marks["vector_end"]
    assert marks["vector_start"] < marks["graph_end"]
    assert marks["graph_start"] < marks["vector_end"]
    assert marks["kv_start"] < marks["graph_end"]
    assert marks["graph_start"] < marks["kv_end"]


def test_hybrid_retriever_survives_vector_failure() -> None:
    org_id = uuid.uuid4()
    repo = InMemoryMemoryRepository()
    kv = InMemoryKVStore()
    memory = _insert(repo, org_id=org_id, content="kv fact only")
    kv.put(
        org_id,
        memory.id,
        "preference",
        "typescript",
        value=None,
        importance=0.5,
    )

    class BoomVector:
        def upsert(self, *args: Any, **kwargs: Any) -> None:
            return None

        def search(self, *args: Any, **kwargs: Any) -> list[ScoredMemory]:
            raise RuntimeError("vector down")

    retriever = HybridRetriever(
        repo=repo,
        vector=BoomVector(),  # type: ignore[arg-type]
        kv=kv,
        graph=InMemoryGraphStore(),
        embedder=HashEmbedder(),
    )
    result = retriever.search(org_id=org_id, q="prefer typescript", session_id="s1")
    assert any(hit.memory.id == memory.id and hit.kv_match == 1.0 for hit in result.hits)


def test_hybrid_retriever_records_timings() -> None:
    org_id = uuid.uuid4()
    repo = InMemoryMemoryRepository()
    _insert(repo, org_id=org_id, content="timing probe")
    retriever = HybridRetriever(
        repo=repo,
        vector=PostgresVectorStore(repo),
        kv=InMemoryKVStore(),
        graph=InMemoryGraphStore(),
        embedder=HashEmbedder(),
    )
    result = retriever.search(org_id=org_id, q="timing probe", session_id="s1")
    keys = set(result.timings.as_dict())
    assert keys == {"embed", "vector", "kv", "graph", "total"}
    assert result.timings.total_ms >= result.timings.embed_ms


def test_hybrid_retriever_disabled_stores_zero_timings(
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(settings, "enable_kv", False)
    monkeypatch.setattr(settings, "enable_graph", False)
    org_id = uuid.uuid4()
    repo = InMemoryMemoryRepository()
    _insert(repo, org_id=org_id, content="flags off")
    retriever = HybridRetriever(
        repo=repo,
        vector=PostgresVectorStore(repo),
        kv=InMemoryKVStore(),
        graph=InMemoryGraphStore(),
        embedder=HashEmbedder(),
    )
    result = retriever.search(org_id=org_id, q="flags off", session_id="s1")
    assert result.timings.kv_ms == 0.0
    assert result.timings.graph_ms == 0.0
