from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from memory_api.db.deps import get_api_key_store, get_repository
from memory_api.db.repository import InMemoryMemoryRepository
from memory_api.main import app
from memory_api.services.api_keys import InMemoryApiKeyStore, generate_api_key
from memory_api.services.embedding import HashEmbedder, get_embedder


@pytest.fixture
def repo() -> InMemoryMemoryRepository:
    return InMemoryMemoryRepository()


@pytest.fixture
def keys() -> InMemoryApiKeyStore:
    return InMemoryApiKeyStore()


@pytest.fixture
def org_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def raw_key(keys: InMemoryApiKeyStore, org_id: uuid.UUID) -> str:
    raw = generate_api_key()
    keys.add(org_id=org_id, raw_key=raw)
    return raw


@pytest.fixture
def client(repo: InMemoryMemoryRepository, keys: InMemoryApiKeyStore) -> TestClient:
    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_embedder] = lambda: HashEmbedder()
    app.dependency_overrides[get_api_key_store] = lambda: keys
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
