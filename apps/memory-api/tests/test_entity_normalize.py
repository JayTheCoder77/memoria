from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from memory_api.db.models import KvFactHistory, Memory, MemoryType
from memory_api.db.repository import InMemoryMemoryRepository
from memory_api.services.dedup import persist_candidate
from memory_api.services.embedding import HashEmbedder
from memory_api.services.entities import normalize_entity
from memory_api.services.extraction import Candidate
from memory_api.services.kv_fanout import persist_kv_facts
from memory_api.stores.graph import InMemoryGraphStore
from memory_api.stores.kv import InMemoryKVStore


def test_kv_fact_history_columns() -> None:
    assert KvFactHistory.__tablename__ == "kv_fact_history"
    assert set(KvFactHistory.__table__.columns.keys()) == {
        "id",
        "org_id",
        "user_id",
        "fact_type",
        "entity",
        "value",
        "memory_id",
        "valid_from",
        "valid_to",
    }


def test_normalize_entity_strips_punctuation_and_keeps_internal_hyphens() -> None:
    assert normalize_entity("  Berlin! ") == "berlin"
    assert normalize_entity("well-known!") == "well-known"
    assert normalize_entity("New   York") == "new york"


def test_second_kv_put_keeps_previous_value_in_history() -> None:
    store = InMemoryKVStore()
    org_id = uuid.uuid4()
    first = uuid.uuid4()
    second = uuid.uuid4()
    store.put(org_id, first, "city", "berlin", value="berlin", importance=0.5)
    store.put(org_id, second, "city", "berlin", value="lisbon", importance=0.5)

    current = store.by_org(org_id)
    assert len(current) == 1
    assert current[0].value == "lisbon"

    closed = [row for row in store.history(org_id) if row.value == "berlin"]
    assert len(closed) == 1
    assert closed[0].valid_to is not None
    assert closed[0].user_id == ""
    assert closed[0].fact_type == "city"
    assert closed[0].entity == "berlin"


def test_value_change_without_open_history_keeps_previous_value() -> None:
    store = InMemoryKVStore()
    org_id = uuid.uuid4()
    store.put(org_id, uuid.uuid4(), "city", "berlin", value="berlin", importance=0.5)
    store._history.clear()

    store.put(org_id, uuid.uuid4(), "city", "berlin", value="lisbon", importance=0.5)

    current = store.by_org(org_id)
    assert len(current) == 1
    assert current[0].value == "lisbon"
    closed = [row for row in store.history(org_id) if row.value == "berlin"]
    assert len(closed) == 1
    assert closed[0].valid_to is not None


def test_kv_and_graph_normalize_entities_before_insert() -> None:
    org_id = uuid.uuid4()
    kv = InMemoryKVStore()
    kv.put(org_id, uuid.uuid4(), "city", "  Berlin! ", value="de", importance=0.5)
    hit = kv.get(org_id, "city", "berlin")
    assert hit is not None
    assert hit.entity == "berlin"

    graph = InMemoryGraphStore()
    graph.add_edge(org_id, "  Berlin! ", "lives_in", "Lisbon.", memory_id=None)
    edges = graph.list_edges(org_id)
    assert len(edges) == 1
    assert edges[0].subject_key == "berlin"
    assert edges[0].object_key == "lisbon"


def test_kv_fanout_normalizes_entity_before_put() -> None:
    repo = InMemoryMemoryRepository()
    memory, _ = persist_candidate(
        repo=repo,
        embedder=HashEmbedder(),
        org_id=uuid.uuid4(),
        session_id="s1",
        candidate=Candidate(content="city", memory_type=MemoryType.semantic),
    )
    assert isinstance(memory, Memory)
    kv = MagicMock()
    persist_kv_facts(
        kv=kv,
        memory=memory,
        candidate=Candidate(
            content=memory.content,
            memory_type=MemoryType.semantic,
            kv_triples=[{"fact_type": "city", "entity": "  Berlin! ", "value": "de"}],
        ),
    )
    assert kv.put.call_args.args[3] == "berlin"
