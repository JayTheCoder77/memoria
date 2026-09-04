from __future__ import annotations

import uuid

from memory_api.stores.noop import NoOpGraphStore, NoOpKVStore


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
