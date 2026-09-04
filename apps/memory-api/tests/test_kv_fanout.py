import uuid
from unittest.mock import MagicMock

from memory_api.db.models import Memory, MemoryType
from memory_api.db.repository import InMemoryMemoryRepository
from memory_api.services.embedding import HashEmbedder
from memory_api.services.extraction import Candidate
from memory_api.services.dedup import persist_candidate
from memory_api.services.kv_fanout import persist_kv_facts
from memory_api.stores.kv import InMemoryKVStore


def _memory() -> Memory:
    repo = InMemoryMemoryRepository()
    memory, _ = persist_candidate(
        repo=repo,
        embedder=HashEmbedder(),
        org_id=uuid.uuid4(),
        session_id="s1",
        candidate=Candidate(
            content="We prefer pytest over unittest in this repo.",
            memory_type=MemoryType.semantic,
        ),
    )
    return memory


def test_persist_kv_facts_writes_heuristic_triple() -> None:
    kv = InMemoryKVStore()
    memory = _memory()
    persist_kv_facts(
        kv=kv,
        memory=memory,
        candidate=Candidate(
            content=memory.content,
            memory_type=MemoryType.semantic,
        ),
    )
    assert kv.get(memory.org_id, "preference", "pytest") is not None


def test_persist_kv_facts_survives_resolve_error(monkeypatch) -> None:
    memory = _memory()
    kv = InMemoryKVStore()

    def _raise(_candidate: Candidate) -> None:
        raise RuntimeError("resolve failed")

    monkeypatch.setattr(
        "memory_api.services.kv_fanout.resolve_kv_triples",
        _raise,
    )
    persist_kv_facts(
        kv=kv,
        memory=memory,
        candidate=Candidate(
            content=memory.content,
            memory_type=MemoryType.semantic,
        ),
    )


def test_persist_kv_facts_survives_put_error() -> None:
    memory = _memory()
    kv = MagicMock()
    kv.put.side_effect = RuntimeError("db down")
    persist_kv_facts(
        kv=kv,
        memory=memory,
        candidate=Candidate(
            content=memory.content,
            memory_type=MemoryType.semantic,
            kv_triples=[{"fact_type": "preference", "entity": "pytest"}],
        ),
    )
    kv.put.assert_called()


def test_persist_kv_facts_noop_when_flag_off(monkeypatch) -> None:
    from memory_api.config import settings

    monkeypatch.setattr(settings, "enable_kv", False)
    kv = InMemoryKVStore()
    memory = _memory()
    persist_kv_facts(
        kv=kv,
        memory=memory,
        candidate=Candidate(
            content=memory.content,
            memory_type=MemoryType.semantic,
            kv_triples=[{"fact_type": "preference", "entity": "pytest"}],
        ),
    )
    assert kv.get(memory.org_id, "preference", "pytest") is None
