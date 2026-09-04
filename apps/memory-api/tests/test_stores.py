from __future__ import annotations

import uuid

from memory_api.db.models import KvFact, MemoryType
from memory_api.db.repository import InMemoryMemoryRepository
from memory_api.stores.noop import NoOpGraphStore, NoOpKVStore
from memory_api.stores.vector import PostgresVectorStore


def test_kv_fact_model_maps_kv_facts_table() -> None:
    assert KvFact.__tablename__ == "kv_facts"
    column_names = set(KvFact.__table__.columns.keys())
    assert column_names == {
        "id",
        "org_id",
        "memory_id",
        "user_key",
        "fact_type",
        "entity",
        "value",
        "importance",
        "created_at",
        "updated_at",
    }


def test_noop_kv_returns_empty() -> None:
    store = NoOpKVStore()
    org_id = uuid.uuid4()
    store.put(
        org_id,
        uuid.uuid4(),
        "preference",
        "typescript",
        value="ts",
        importance=0.8,
    )
    assert store.get(org_id, "preference", "typescript") is None
    assert store.search_keys(org_id, [("preference", "typescript")]) == []
    assert store.by_org(org_id) == []


def test_noop_graph_returns_empty_neighbors() -> None:
    store = NoOpGraphStore()
    org_id = uuid.uuid4()
    node_id = store.upsert_node(org_id, "ava", "person")
    edge_id = store.add_edge(
        org_id, "ava", "lives_in", "lisbon", memory_id=uuid.uuid4()
    )
    assert isinstance(node_id, uuid.UUID)
    assert isinstance(edge_id, uuid.UUID)
    assert store.neighbors(org_id, "ava") == []
    assert store.memories_for_subgraph(org_id, ["ava"]) == []


def test_vector_store_search_delegates_to_repository() -> None:
    repo = InMemoryMemoryRepository()
    org_id = uuid.uuid4()
    memory = repo.insert(
        org_id=org_id,
        session_id="s1",
        memory_type=MemoryType.semantic,
        content="preferred language is typescript",
        embedding=[1.0, 0.0, 0.0],
        importance=0.7,
        source_metadata={},
    )
    store = PostgresVectorStore(repo)
    store.upsert(memory.id, memory.embedding, {})
    hits = store.search(org_id, [1.0, 0.0, 0.0], session_id="s1", limit=5)
    assert len(hits) == 1
    assert hits[0].memory.id == memory.id
    assert hits[0].similarity == 1.0
