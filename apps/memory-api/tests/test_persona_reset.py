from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from memory_api.db.deps import (
    get_api_key_store,
    get_event_store,
    get_graph_store,
    get_kv_store,
    get_repository,
)
from memory_api.db.events import InMemoryEventStore
from memory_api.db.models import EventStatus, MemoryType
from memory_api.db.repository import InMemoryMemoryRepository
from memory_api.main import app
from memory_api.services.api_keys import InMemoryApiKeyStore, generate_api_key
from memory_api.services.embedding import HashEmbedder, get_embedder
from memory_api.stores.graph import InMemoryGraphStore
from memory_api.stores.kv import InMemoryKVStore


def _client(
    *,
    events: InMemoryEventStore,
    repo: InMemoryMemoryRepository,
    keys: InMemoryApiKeyStore,
    kv: InMemoryKVStore,
    graph: InMemoryGraphStore,
) -> TestClient:
    app.dependency_overrides[get_event_store] = lambda: events
    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_embedder] = lambda: HashEmbedder()
    app.dependency_overrides[get_api_key_store] = lambda: keys
    app.dependency_overrides[get_kv_store] = lambda: kv
    app.dependency_overrides[get_graph_store] = lambda: graph
    return TestClient(app)


def test_pending_count_is_org_scoped_and_omits_event_content() -> None:
    events = InMemoryEventStore()
    keys = InMemoryApiKeyStore()
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()
    key_a = generate_api_key()
    key_b = generate_api_key()
    keys.add(org_id=org_a, raw_key=key_a)
    keys.add(org_id=org_b, raw_key=key_b)
    client = _client(
        events=events,
        repo=InMemoryMemoryRepository(),
        keys=keys,
        kv=InMemoryKVStore(),
        graph=InMemoryGraphStore(),
    )
    secret = "Morgan prefers private beaches"
    try:
        queued = client.post(
            "/events",
            headers={"Authorization": f"Bearer {key_a}"},
            json={
                "session_id": "sess-1",
                "event_type": "message",
                "user_id": "morgan",
                "payload": {"content": secret},
            },
        )
        assert queued.status_code == 202
        own = client.get(
            "/events/pending",
            headers={"Authorization": f"Bearer {key_a}"},
            params={"session_id": "sess-1"},
        )
        other = client.get(
            "/events/pending",
            headers={"Authorization": f"Bearer {key_b}"},
            params={"session_id": "sess-1"},
        )
        assert own.status_code == 200
        assert own.json() == {"pending": 1, "failed": 0}
        assert secret not in own.text
        assert other.status_code == 200
        assert other.json() == {"pending": 0, "failed": 0}
        events.pending("sess-1")[0].status = EventStatus.processing
        processing = client.get(
            "/events/pending",
            headers={"Authorization": f"Bearer {key_a}"},
            params={"session_id": "sess-1"},
        )
        row = next(item for item in events._rows if item.session_id == "sess-1")
        row.status = EventStatus.processed
        drained = client.get(
            "/events/pending",
            headers={"Authorization": f"Bearer {key_a}"},
            params={"session_id": "sess-1"},
        )
        row.status = EventStatus.failed
        failed = client.get(
            "/events/pending",
            headers={"Authorization": f"Bearer {key_a}"},
            params={"session_id": "sess-1"},
        )
        other_failed = client.get(
            "/events/pending",
            headers={"Authorization": f"Bearer {key_b}"},
            params={"session_id": "sess-1"},
        )
    finally:
        app.dependency_overrides.clear()

    assert processing.status_code == 200
    assert processing.json() == {"pending": 1, "failed": 0}
    assert drained.status_code == 200
    assert drained.json() == {"pending": 0, "failed": 0}
    assert failed.status_code == 200
    assert failed.json() == {"pending": 0, "failed": 1}
    assert secret not in failed.text
    assert set(failed.json()) == {"pending", "failed"}
    assert other_failed.json() == {"pending": 0, "failed": 0}


def test_delete_routes_clear_one_users_memories_kv_and_graph() -> None:
    repo = InMemoryMemoryRepository()
    kv = InMemoryKVStore()
    graph = InMemoryGraphStore()
    keys = InMemoryApiKeyStore()
    org_id = uuid.uuid4()
    other_org = uuid.uuid4()
    raw_key = generate_api_key()
    keys.add(org_id=org_id, raw_key=raw_key)
    embedder = HashEmbedder()
    morgan = repo.insert(
        org_id=org_id,
        session_id="s",
        memory_type=MemoryType.semantic,
        content="Morgan lives in Austin",
        embedding=embedder.embed("Morgan lives in Austin"),
        importance=0.8,
        source_metadata={},
        user_id="morgan",
    )
    alex = repo.insert(
        org_id=org_id,
        session_id="s",
        memory_type=MemoryType.semantic,
        content="Alex lives in Boston",
        embedding=embedder.embed("Alex lives in Boston"),
        importance=0.8,
        source_metadata={},
        user_id="alex",
    )
    outsider = repo.insert(
        org_id=other_org,
        session_id="s",
        memory_type=MemoryType.semantic,
        content="Other org fact",
        embedding=embedder.embed("Other org fact"),
        importance=0.8,
        source_metadata={},
        user_id="morgan",
    )
    kv.put(org_id, morgan.id, "city", "home", value="Austin", importance=0.9, user_id="morgan")
    kv.put(org_id, alex.id, "city", "home", value="Boston", importance=0.9, user_id="alex")
    graph.add_edge(
        org_id, "morgan", "lives_in", "austin", memory_id=morgan.id, user_id="morgan"
    )
    graph.add_edge(org_id, "alex", "lives_in", "boston", memory_id=alex.id, user_id="alex")
    client = _client(
        events=InMemoryEventStore(),
        repo=repo,
        keys=keys,
        kv=kv,
        graph=graph,
    )
    try:
        for path in ("/graph", "/kv-facts", "/memories"):
            response = client.delete(
                path,
                headers={"Authorization": f"Bearer {raw_key}"},
                params={"user_id": "morgan"},
            )
            assert response.status_code == 204
    finally:
        app.dependency_overrides.clear()

    assert repo.list(org_id=org_id, user_id="morgan") == []
    assert kv.by_org(org_id, user_id="morgan") == []
    assert graph.list_edges(org_id, user_id="morgan", valid_only=False) == []
    morgan_nodes = [
        node.entity_key
        for node in graph._nodes.values()
        if node.org_id == org_id and node.user_id == "morgan"
    ]
    assert morgan_nodes == []
    assert any(node.user_id == "alex" for node in graph._nodes.values())
    assert [row.id for row in repo.list(org_id=org_id, user_id="alex")] == [alex.id]
    assert len(kv.by_org(org_id, user_id="alex")) == 1
    assert len(graph.list_edges(org_id, user_id="alex", valid_only=False)) == 1
    assert [row.id for row in repo.list(org_id=other_org, user_id="morgan")] == [outsider.id]
