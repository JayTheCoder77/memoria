from __future__ import annotations

import time
import uuid
from datetime import timedelta

from memory_api.db.models import MemoryType
from memory_api.db.repository import InMemoryMemoryRepository
from memory_api.services.embedding import HashEmbedder
from memory_api.services.hybrid_search import HybridRetriever
from memory_api.stores.graph import InMemoryGraphStore
from memory_api.stores.kv import InMemoryKVStore
from memory_api.stores.vector import PostgresVectorStore


def _retriever(
    repo: InMemoryMemoryRepository,
    kv: InMemoryKVStore,
    graph: InMemoryGraphStore,
) -> HybridRetriever:
    return HybridRetriever(
        repo=repo,
        vector=PostgresVectorStore(repo),
        kv=kv,
        graph=graph,
        embedder=HashEmbedder(),
    )


def _insert(
    repo: InMemoryMemoryRepository,
    org_id: uuid.UUID,
    content: str,
) -> object:
    embedder = HashEmbedder()
    memory = repo.insert(
        org_id=org_id,
        session_id="s1",
        memory_type=MemoryType.semantic,
        content=content,
        embedding=embedder.embed(content),
        importance=0.5,
        source_metadata={},
    )
    return memory


def test_benchmark_fact_lookup_kv() -> None:
    org_id = uuid.uuid4()
    repo = InMemoryMemoryRepository()
    kv = InMemoryKVStore()
    graph = InMemoryGraphStore()
    for i in range(25):
        _insert(repo, org_id, f"What language do they prefer typescript decoy {i}")
    target = _insert(repo, org_id, "zzz-kv-only-payload-not-the-query")
    kv.put(
        org_id,
        target.id,
        "preference",
        "typescript",
        value=None,
        importance=0.5,
    )
    result = _retriever(repo, kv, graph).search(
        org_id=org_id, q="prefer typescript", session_id="s1", limit=10
    )
    hit = next(h for h in result.hits if h.memory.id == target.id)
    assert hit.kv_match == 1.0
    assert result.timings.as_dict()["kv"] >= 0


def test_benchmark_relationship_graph() -> None:
    org_id = uuid.uuid4()
    repo = InMemoryMemoryRepository()
    kv = InMemoryKVStore()
    graph = InMemoryGraphStore()
    target = _insert(repo, org_id, "one hop ava likes coding")
    graph.add_edge(org_id, "ava", "likes", "coding", memory_id=target.id)
    result = _retriever(repo, kv, graph).search(
        org_id=org_id, q="tell me about ava", session_id="s1"
    )
    hit = next(h for h in result.hits if h.memory.id == target.id)
    assert hit.graph_hops == 1


def test_benchmark_semantic_vector() -> None:
    org_id = uuid.uuid4()
    repo = InMemoryMemoryRepository()
    content = "the deploy pipeline uses uv and pytest"
    memory = _insert(repo, org_id, content)
    result = _retriever(repo, InMemoryKVStore(), InMemoryGraphStore()).search(
        org_id=org_id, q=content, session_id="s1"
    )
    assert result.hits[0].memory.id == memory.id
    assert result.hits[0].vector_hit is True


def test_benchmark_temporal_as_of() -> None:
    org_id = uuid.uuid4()
    repo = InMemoryMemoryRepository()
    kv = InMemoryKVStore()
    graph = InMemoryGraphStore()
    berlin = _insert(repo, org_id, "lived in berlin")
    munich = _insert(repo, org_id, "lived in munich")
    graph.add_edge(org_id, "user", "lives_in", "berlin", memory_id=berlin.id)
    berlin_from = next(
        edge.valid_from
        for edge in graph.neighbors(
            org_id, "user", hops=1, valid_only=False
        )
        if edge.object_key == "berlin" and edge.valid_from is not None
    )
    time.sleep(0.02)
    graph.add_edge(org_id, "user", "lives_in", "munich", memory_id=munich.id)
    as_of = berlin_from + timedelta(microseconds=1)
    historical = _retriever(repo, kv, graph).search(
        org_id=org_id,
        q="lives in berlin",
        session_id="s1",
        as_of=as_of,
    )
    hist_ids = [h.memory.id for h in historical.hits]
    assert berlin.id in hist_ids
    current = _retriever(repo, kv, graph).search(
        org_id=org_id, q="lives in munich", session_id="s1"
    )
    current_ids = [h.memory.id for h in current.hits]
    assert munich.id in current_ids
    assert historical.timings.as_dict()["graph"] >= 0
