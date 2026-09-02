from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from memory_api.db.deps import get_repository
from memory_api.db.repository import InMemoryMemoryRepository
from memory_api.main import app
from memory_api.services.embedding import HashEmbedder, get_embedder


@pytest.fixture
def repo() -> InMemoryMemoryRepository:
    return InMemoryMemoryRepository()


@pytest.fixture
def client(repo: InMemoryMemoryRepository) -> TestClient:
    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_embedder] = lambda: HashEmbedder()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def org_id() -> str:
    return str(uuid.uuid4())


def test_write_then_search_returns_the_same_memory(client: TestClient, org_id: str) -> None:
    content = "the deploy pipeline uses uv and pytest"
    created = client.post(
        "/memories",
        json={
            "org_id": org_id,
            "session_id": "repo-memoria",
            "memory_type": "semantic",
            "content": content,
            "importance": 0.9,
        },
    )
    assert created.status_code == 201
    memory_id = created.json()["id"]

    search = client.get(
        "/memories/search",
        params={"org_id": org_id, "q": content, "session_id": "repo-memoria"},
    )
    assert search.status_code == 200
    hits = search.json()["memories"]
    assert hits[0]["id"] == memory_id
    assert hits[0]["content"] == content


def test_search_does_not_return_another_orgs_memories(client: TestClient) -> None:
    org_a = str(uuid.uuid4())
    org_b = str(uuid.uuid4())
    shared_content = "api keys are stored hashed"
    write_a = client.post(
        "/memories",
        json={
            "org_id": org_a,
            "session_id": "s1",
            "memory_type": "procedural",
            "content": shared_content,
        },
    )
    write_b = client.post(
        "/memories",
        json={
            "org_id": org_b,
            "session_id": "s1",
            "memory_type": "procedural",
            "content": shared_content,
        },
    )
    assert write_a.status_code == 201
    assert write_b.status_code == 201

    search_a = client.get(
        "/memories/search",
        params={"org_id": org_a, "q": shared_content, "session_id": "s1"},
    )
    ids = {hit["id"] for hit in search_a.json()["memories"]}
    assert write_a.json()["id"] in ids
    assert write_b.json()["id"] not in ids


def test_update_changes_content(client: TestClient, org_id: str) -> None:
    created = client.post(
        "/memories",
        json={
            "org_id": org_id,
            "session_id": "s1",
            "memory_type": "episodic",
            "content": "original note",
        },
    )
    memory_id = created.json()["id"]

    updated = client.patch(
        f"/memories/{memory_id}",
        params={"org_id": org_id},
        json={"content": "corrected note", "importance": 0.4},
    )
    assert updated.status_code == 200
    assert updated.json()["content"] == "corrected note"
    assert updated.json()["importance"] == 0.4


def test_update_is_scoped_to_org(client: TestClient) -> None:
    owner = str(uuid.uuid4())
    other = str(uuid.uuid4())
    created = client.post(
        "/memories",
        json={
            "org_id": owner,
            "session_id": "s1",
            "memory_type": "semantic",
            "content": "secret",
        },
    )
    memory_id = created.json()["id"]

    patched = client.patch(
        f"/memories/{memory_id}",
        params={"org_id": other},
        json={"content": "stolen"},
    )
    assert patched.status_code == 404


def test_delete_forgets_memory(client: TestClient, org_id: str) -> None:
    created = client.post(
        "/memories",
        json={
            "org_id": org_id,
            "session_id": "s1",
            "memory_type": "semantic",
            "content": "forget me",
        },
    )
    memory_id = created.json()["id"]

    deleted = client.delete(f"/memories/{memory_id}", params={"org_id": org_id})
    assert deleted.status_code == 204

    search = client.get(
        "/memories/search",
        params={"org_id": org_id, "q": "forget me", "session_id": "s1"},
    )
    assert search.json()["memories"] == []


def test_write_requires_org_id(client: TestClient) -> None:
    response = client.post(
        "/memories",
        json={
            "session_id": "s1",
            "memory_type": "semantic",
            "content": "no org",
        },
    )
    assert response.status_code == 422
