import uuid
from unittest.mock import MagicMock

from memory_api.db.models import Memory, MemoryType
from memory_api.db.repository import InMemoryMemoryRepository
from memory_api.services.dedup import persist_candidate
from memory_api.services.embedding import HashEmbedder
from memory_api.services.extraction import Candidate
from memory_api.services.graph_fanout import persist_graph_facts
from memory_api.stores.graph import InMemoryGraphStore


def _memory() -> Memory:
    repo = InMemoryMemoryRepository()
    memory, _ = persist_candidate(
        repo=repo,
        embedder=HashEmbedder(),
        org_id=uuid.uuid4(),
        session_id="s1",
        candidate=Candidate(
            content="Ava lives in Berlin.",
            memory_type=MemoryType.semantic,
        ),
    )
    return memory


def test_persist_graph_facts_writes_heuristic_edge() -> None:
    graph = InMemoryGraphStore()
    memory = _memory()
    persist_graph_facts(
        graph=graph,
        memory=memory,
        candidate=Candidate(
            content=memory.content,
            memory_type=MemoryType.semantic,
        ),
    )
    edges = graph.neighbors(memory.org_id, "user", hops=1)
    assert any(
        e.relation == "lives_in" and e.object_key == "berlin" and e.memory_id == memory.id
        for e in edges
    )


def test_persist_graph_facts_survives_resolve_error(monkeypatch) -> None:
    memory = _memory()
    graph = InMemoryGraphStore()

    def _raise(_candidate: Candidate) -> None:
        raise RuntimeError("resolve failed")

    monkeypatch.setattr(
        "memory_api.services.graph_fanout.resolve_graph_triples",
        _raise,
    )
    persist_graph_facts(
        graph=graph,
        memory=memory,
        candidate=Candidate(
            content=memory.content,
            memory_type=MemoryType.semantic,
        ),
    )


def test_persist_graph_facts_survives_add_edge_error() -> None:
    memory = _memory()
    graph = MagicMock()
    graph.add_edge.side_effect = RuntimeError("db down")
    persist_graph_facts(
        graph=graph,
        memory=memory,
        candidate=Candidate(
            content=memory.content,
            memory_type=MemoryType.semantic,
            graph_triples=[
                {"subject": "user", "relation": "lives_in", "object": "berlin"},
            ],
        ),
    )
    graph.add_edge.assert_called()


def test_persist_graph_facts_noop_when_flag_off(monkeypatch) -> None:
    from memory_api.config import settings

    monkeypatch.setattr(settings, "enable_graph", False)
    graph = InMemoryGraphStore()
    memory = _memory()
    persist_graph_facts(
        graph=graph,
        memory=memory,
        candidate=Candidate(
            content=memory.content,
            memory_type=MemoryType.semantic,
            graph_triples=[
                {"subject": "user", "relation": "lives_in", "object": "berlin"},
            ],
        ),
    )
    assert graph.neighbors(memory.org_id, "user", hops=1) == []
