from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from memory_api.db.deps import get_api_key_store, get_graph_store, get_kv_store, get_repository
from memory_api.db.models import Org
from memory_api.db.repository import InMemoryMemoryRepository
from memory_api.main import app
from memory_api.routers.memories import _org_llm_key
from memory_api.services.api_keys import InMemoryApiKeyStore, generate_api_key
from memory_api.services.embedding import HashEmbedder, embed_text, get_embedder
from memory_api.stores.graph import InMemoryGraphStore
from memory_api.stores.kv import InMemoryKVStore


@pytest.fixture
def repo() -> InMemoryMemoryRepository:
    return InMemoryMemoryRepository()


@pytest.fixture
def keys() -> InMemoryApiKeyStore:
    return InMemoryApiKeyStore()


@pytest.fixture
def kv() -> InMemoryKVStore:
    return InMemoryKVStore()


@pytest.fixture
def org_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def raw_key(keys: InMemoryApiKeyStore, org_id: uuid.UUID) -> str:
    raw = generate_api_key()
    keys.add(org_id=org_id, raw_key=raw)
    return raw


@pytest.fixture
def graph() -> InMemoryGraphStore:
    return InMemoryGraphStore()


@pytest.fixture
def client(
    repo: InMemoryMemoryRepository, keys: InMemoryApiKeyStore, kv: InMemoryKVStore, graph: InMemoryGraphStore
) -> TestClient:
    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_embedder] = lambda: HashEmbedder()
    app.dependency_overrides[get_api_key_store] = lambda: keys
    app.dependency_overrides[get_kv_store] = lambda: kv
    app.dependency_overrides[get_graph_store] = lambda: graph
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _auth(raw_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {raw_key}"}


def test_write_then_search_returns_the_same_memory(
    client: TestClient, org_id: uuid.UUID, raw_key: str
) -> None:
    content = "the deploy pipeline uses uv and pytest"
    created = client.post(
        "/memories",
        headers=_auth(raw_key),
        json={
            "session_id": "repo-memoria",
            "memory_type": "semantic",
            "content": content,
            "importance": 0.9,
        },
    )
    assert created.status_code == 201
    memory_id = created.json()["id"]
    assert created.json()["org_id"] == str(org_id)

    search = client.get(
        "/memories/search",
        headers=_auth(raw_key),
        params={"q": content, "session_id": "repo-memoria"},
    )
    assert search.status_code == 200
    hits = search.json()["memories"]
    assert hits[0]["id"] == memory_id
    assert hits[0]["content"] == content


def test_search_does_not_return_another_orgs_memories(
    client: TestClient, keys: InMemoryApiKeyStore
) -> None:
    org_a = uuid.uuid4()
    org_b = uuid.uuid4()
    key_a = generate_api_key()
    key_b = generate_api_key()
    keys.add(org_id=org_a, raw_key=key_a)
    keys.add(org_id=org_b, raw_key=key_b)
    shared_content = "api keys are stored hashed"
    write_a = client.post(
        "/memories",
        headers=_auth(key_a),
        json={
            "session_id": "s1",
            "memory_type": "procedural",
            "content": shared_content,
        },
    )
    write_b = client.post(
        "/memories",
        headers=_auth(key_b),
        json={
            "session_id": "s1",
            "memory_type": "procedural",
            "content": shared_content,
        },
    )
    assert write_a.status_code == 201
    assert write_b.status_code == 201

    search_a = client.get(
        "/memories/search",
        headers=_auth(key_a),
        params={"q": shared_content, "session_id": "s1"},
    )
    ids = {hit["id"] for hit in search_a.json()["memories"]}
    assert write_a.json()["id"] in ids
    assert write_b.json()["id"] not in ids


def test_update_changes_content(client: TestClient, raw_key: str) -> None:
    created = client.post(
        "/memories",
        headers=_auth(raw_key),
        json={
            "session_id": "s1",
            "memory_type": "episodic",
            "content": "original note",
        },
    )
    memory_id = created.json()["id"]

    updated = client.patch(
        f"/memories/{memory_id}",
        headers=_auth(raw_key),
        json={"content": "corrected note", "importance": 0.4},
    )
    assert updated.status_code == 200
    assert updated.json()["content"] == "corrected note"
    assert updated.json()["importance"] == 0.4


def test_update_is_scoped_to_org(client: TestClient, keys: InMemoryApiKeyStore) -> None:
    owner = uuid.uuid4()
    other = uuid.uuid4()
    owner_key = generate_api_key()
    other_key = generate_api_key()
    keys.add(org_id=owner, raw_key=owner_key)
    keys.add(org_id=other, raw_key=other_key)
    created = client.post(
        "/memories",
        headers=_auth(owner_key),
        json={
            "session_id": "s1",
            "memory_type": "semantic",
            "content": "secret",
        },
    )
    memory_id = created.json()["id"]

    patched = client.patch(
        f"/memories/{memory_id}",
        headers=_auth(other_key),
        json={"content": "stolen"},
    )
    assert patched.status_code == 404


def test_delete_forgets_memory(client: TestClient, raw_key: str) -> None:
    created = client.post(
        "/memories",
        headers=_auth(raw_key),
        json={
            "session_id": "s1",
            "memory_type": "semantic",
            "content": "forget me",
        },
    )
    memory_id = created.json()["id"]

    deleted = client.delete(f"/memories/{memory_id}", headers=_auth(raw_key))
    assert deleted.status_code == 204

    search = client.get(
        "/memories/search",
        headers=_auth(raw_key),
        params={"q": "forget me", "session_id": "s1"},
    )
    assert search.json()["memories"] == []


def test_write_requires_api_key(client: TestClient) -> None:
    response = client.post(
        "/memories",
        json={
            "session_id": "s1",
            "memory_type": "semantic",
            "content": "no org",
        },
    )
    assert response.status_code == 401


def test_duplicate_remember_reinforces_existing(client: TestClient, raw_key: str) -> None:
    payload = {
        "session_id": "s1",
        "memory_type": "semantic",
        "content": "We prefer pytest over unittest.",
    }
    first = client.post("/memories", headers=_auth(raw_key), json=payload)
    second = client.post("/memories", headers=_auth(raw_key), json=payload)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert second.json()["access_count"] == 1


def test_search_omits_score_details_by_default(
    client: TestClient, raw_key: str
) -> None:
    created = client.post(
        "/memories",
        headers=_auth(raw_key),
        json={
            "session_id": "s1",
            "memory_type": "semantic",
            "content": "explain skeleton probe",
            "importance": 0.7,
        },
    )
    assert created.status_code == 201
    search = client.get(
        "/memories/search",
        headers=_auth(raw_key),
        params={"q": "explain skeleton probe", "session_id": "s1"},
    )
    assert search.status_code == 200
    hit = search.json()["memories"][0]
    assert hit.get("score_details") is None


def test_search_explain_returns_full_score_details_keys(
    client: TestClient, raw_key: str
) -> None:
    created = client.post(
        "/memories",
        headers=_auth(raw_key),
        json={
            "session_id": "s1",
            "memory_type": "semantic",
            "content": "explain skeleton probe",
            "importance": 0.7,
        },
    )
    assert created.status_code == 201
    search = client.get(
        "/memories/search",
        headers=_auth(raw_key),
        params={"q": "explain skeleton probe", "session_id": "s1", "explain": True},
    )
    assert search.status_code == 200
    details = search.json()["memories"][0]["score_details"]
    assert details["sources"] == ["vector"]
    assert details["kv_match"] is None
    assert details["graph_hops"] is None
    assert details["vector_similarity"] == details["relevance"]
    assert details["importance"] == 0.7
    assert set(details["weights"]) == {"relevance", "importance", "recency"}
    assert details["weights"]["relevance"] == 0.6


def test_search_kv_union_respects_session_scope(
    client: TestClient, raw_key: str
) -> None:
    other_session = client.post(
        "/memories",
        headers=_auth(raw_key),
        json={
            "session_id": "s-other",
            "content": "zzz-kv-only-payload-not-the-query",
            "kv_triples": [{"fact_type": "preference", "entity": "typescript"}],
        },
    )
    assert other_session.status_code == 201
    other_id = other_session.json()["id"]

    search = client.get(
        "/memories/search",
        headers=_auth(raw_key),
        params={
            "q": "prefer typescript",
            "session_id": "s1",
            "explain": True,
        },
    )
    assert search.status_code == 200
    ids = {row["id"] for row in search.json()["memories"]}
    assert other_id not in ids


def test_org_llm_key_decrypt_failure_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    org = Org(id=uuid.uuid4(), openrouter_key_ciphertext="cipher")

    class FakeSession:
        def get(self, model: type, pk: uuid.UUID) -> Org:
            return org

    class FakeRepo:
        _session = FakeSession()

    def boom(_ciphertext: str) -> str:
        raise RuntimeError("decrypt failed")

    monkeypatch.setattr("memory_api.routers.memories.decrypt_secret", boom)
    assert _org_llm_key(FakeRepo(), org.id) == (None, None)


def test_search_survives_org_key_decrypt_failure(
    monkeypatch: pytest.MonkeyPatch,
    keys: InMemoryApiKeyStore,
    kv: InMemoryKVStore,
    graph: InMemoryGraphStore,
    org_id: uuid.UUID,
    raw_key: str,
) -> None:
    org = Org(
        id=org_id,
        openrouter_key_ciphertext="cipher",
        openrouter_model="anthropic/claude-sonnet-4",
    )
    repo = InMemoryMemoryRepository()
    repo._session = type(
        "FakeSession",
        (),
        {"get": lambda self, model, pk: org if model is Org else None},
    )()

    def boom(_ciphertext: str) -> str:
        raise RuntimeError("decrypt failed")

    monkeypatch.setattr("memory_api.routers.memories.decrypt_secret", boom)

    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_embedder] = lambda: HashEmbedder()
    app.dependency_overrides[get_api_key_store] = lambda: keys
    app.dependency_overrides[get_kv_store] = lambda: kv
    app.dependency_overrides[get_graph_store] = lambda: graph
    with TestClient(app) as client:
        target = client.post(
            "/memories",
            headers=_auth(raw_key),
            json={
                "session_id": "s1",
                "content": "zzz-kv-only-payload-not-the-query",
                "kv_triples": [{"fact_type": "preference", "entity": "typescript"}],
            },
        )
        assert target.status_code == 201
        search = client.get(
            "/memories/search",
            headers=_auth(raw_key),
            params={
                "q": "What language do they prefer typescript",
                "session_id": "s1",
                "explain": True,
                "limit": 1,
            },
        )
        assert search.status_code == 200
        ids = {row["id"] for row in search.json()["memories"]}
        assert target.json()["id"] in ids
    app.dependency_overrides.clear()


def test_search_kv_only_outside_vector_overfetch(
    client: TestClient,
    repo: InMemoryMemoryRepository,
    org_id: uuid.UUID,
    raw_key: str,
) -> None:
    embedder = HashEmbedder()
    query = "What language do they prefer typescript"
    query_embedding = embed_text(query, embedder=embedder)
    for index in range(25):
        repo.insert(
            org_id=org_id,
            session_id="s1",
            memory_type="semantic",
            content=f"decoy-{index}: {query}",
            embedding=query_embedding,
            importance=0.1,
            source_metadata={},
        )

    target = client.post(
        "/memories",
        headers=_auth(raw_key),
        json={
            "session_id": "s1",
            "content": "zzz-kv-only-payload-not-the-query",
            "importance": 1.0,
            "kv_triples": [{"fact_type": "preference", "entity": "typescript"}],
        },
    )
    assert target.status_code == 201
    target_id = target.json()["id"]

    search = client.get(
        "/memories/search",
        headers=_auth(raw_key),
        params={
            "q": query,
            "session_id": "s1",
            "explain": True,
            "limit": 1,
        },
    )
    assert search.status_code == 200
    hits = search.json()["memories"]
    assert hits
    assert target_id in {row["id"] for row in hits}
    kv_hit = next(row for row in hits if row["id"] == target_id)
    assert kv_hit["score_details"]["kv_match"] == 1.0
    assert kv_hit["score_details"]["sources"] == ["kv"]
    assert kv_hit["score_details"]["vector_similarity"] == 0.0


def test_search_unions_kv_hit_when_vector_is_weak(
    client: TestClient, raw_key: str
) -> None:
    decoy = client.post(
        "/memories",
        headers=_auth(raw_key),
        json={
            "session_id": "s1",
            "content": "What language do they prefer typescript",
        },
    )
    target = client.post(
        "/memories",
        headers=_auth(raw_key),
        json={
            "session_id": "s1",
            "content": "zzz-kv-only-payload-not-the-query",
            "kv_triples": [{"fact_type": "preference", "entity": "typescript"}],
        },
    )
    assert decoy.status_code == 201
    assert target.status_code == 201
    search = client.get(
        "/memories/search",
        headers=_auth(raw_key),
        params={
            "q": "What language do they prefer typescript",
            "session_id": "s1",
            "explain": True,
            "limit": 10,
        },
    )
    assert search.status_code == 200
    hits = search.json()["memories"]
    ids = [row["id"] for row in hits]
    assert target.json()["id"] in ids
    kv_hit = next(row for row in hits if row["id"] == target.json()["id"])
    assert kv_hit["score_details"]["kv_match"] == 1.0
    assert "kv" in kv_hit["score_details"]["sources"]


def test_search_explain_vector_only_still_null_kv(
    client: TestClient, raw_key: str
) -> None:
    client.post(
        "/memories",
        headers=_auth(raw_key),
        json={"session_id": "s1", "content": "explain skeleton probe"},
    )
    search = client.get(
        "/memories/search",
        headers=_auth(raw_key),
        params={"q": "explain skeleton probe", "session_id": "s1", "explain": True},
    )
    details = search.json()["memories"][0]["score_details"]
    assert details["kv_match"] is None
    assert details["sources"] == ["vector"]


def test_remember_writes_explicit_kv_triples(
    client: TestClient, raw_key: str, org_id: uuid.UUID, kv: InMemoryKVStore
) -> None:
    created = client.post(
        "/memories",
        headers=_auth(raw_key),
        json={
            "session_id": "s1",
            "memory_type": "semantic",
            "content": "zzz-unrelated-content-for-hash",
            "kv_triples": [{"fact_type": "preference", "entity": "typescript"}],
        },
    )
    assert created.status_code == 201
    fact = kv.get(org_id, "preference", "typescript")
    assert fact is not None
    assert str(fact.memory_id) == created.json()["id"]


def test_remember_still_201_when_kv_put_raises(
    repo: InMemoryMemoryRepository, keys: InMemoryApiKeyStore, graph: InMemoryGraphStore, raw_key: str
) -> None:
    class BoomStore(InMemoryKVStore):
        def put(self, *args, **kwargs) -> None:
            raise RuntimeError("db down")

    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_embedder] = lambda: HashEmbedder()
    app.dependency_overrides[get_api_key_store] = lambda: keys
    app.dependency_overrides[get_kv_store] = lambda: BoomStore()
    app.dependency_overrides[get_graph_store] = lambda: graph
    with TestClient(app) as client:
        created = client.post(
            "/memories",
            headers=_auth(raw_key),
            json={"session_id": "s1", "content": "We prefer pytest over unittest."},
        )
        assert created.status_code == 201
    app.dependency_overrides.clear()


def test_remember_writes_explicit_graph_triples(
    client: TestClient, raw_key: str, org_id: uuid.UUID, graph: InMemoryGraphStore
) -> None:
    created = client.post(
        "/memories",
        headers=_auth(raw_key),
        json={
            "session_id": "s1",
            "memory_type": "semantic",
            "content": "zzz-unrelated-content-for-hash",
            "graph_triples": [
                {"subject": "user", "relation": "lives_in", "object": "berlin"},
            ],
        },
    )
    assert created.status_code == 201
    edges = graph.neighbors(org_id, "user", hops=1)
    assert any(
        e.relation == "lives_in"
        and e.object_key == "berlin"
        and str(e.memory_id) == created.json()["id"]
        for e in edges
    )


def test_remember_still_201_when_graph_add_edge_raises(
    repo: InMemoryMemoryRepository, keys: InMemoryApiKeyStore, kv: InMemoryKVStore, raw_key: str
) -> None:
    class BoomGraph(InMemoryGraphStore):
        def add_edge(self, *args, **kwargs) -> uuid.UUID:
            raise RuntimeError("db down")

    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_embedder] = lambda: HashEmbedder()
    app.dependency_overrides[get_api_key_store] = lambda: keys
    app.dependency_overrides[get_kv_store] = lambda: kv
    app.dependency_overrides[get_graph_store] = lambda: BoomGraph()
    with TestClient(app) as client:
        created = client.post(
            "/memories",
            headers=_auth(raw_key),
            json={
                "session_id": "s1",
                "content": "Ava lives in Berlin.",
                "graph_triples": [
                    {"subject": "user", "relation": "lives_in", "object": "berlin"},
                ],
            },
        )
        assert created.status_code == 201
    app.dependency_overrides.clear()


def test_remember_accepts_agent_memory_type_aliases(client: TestClient, raw_key: str) -> None:
    created = client.post(
        "/memories",
        headers=_auth(raw_key),
        json={
            "session_id": "opencode-local",
            "memory_type": "preference",
            "content": "We prefer bun",
            "importance": "0.7",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["memory_type"] == "semantic"
    assert created.json()["importance"] == 0.7
