from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

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
def raw_key(keys: InMemoryApiKeyStore) -> str:
    raw = generate_api_key()
    keys.add(org_id=uuid.uuid4(), raw_key=raw)
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


def test_search_ranks_important_recent_memory_first(
    client: TestClient, repo: InMemoryMemoryRepository, raw_key: str
) -> None:
    stale = client.post(
        "/memories",
        headers=_auth(raw_key),
        json={
            "session_id": "s1",
            "memory_type": "semantic",
            "content": "shared retrieval text",
            "importance": 0.1,
        },
    )
    fresh = client.post(
        "/memories",
        headers=_auth(raw_key),
        json={
            "session_id": "s1",
            "memory_type": "semantic",
            "content": "shared retrieval text",
            "importance": 0.95,
        },
    )
    assert stale.status_code == 201
    assert fresh.status_code == 201
    for row in repo._rows:
        if str(row.id) == stale.json()["id"]:
            row.created_at = datetime.now(UTC) - timedelta(days=40)

    search = client.get(
        "/memories/search",
        headers=_auth(raw_key),
        params={"q": "shared retrieval text", "session_id": "s1"},
    )
    ids = [hit["id"] for hit in search.json()["memories"]]
    assert ids[0] == fresh.json()["id"]


def test_search_truncates_to_token_budget(client: TestClient, raw_key: str) -> None:
    for index in range(3):
        created = client.post(
            "/memories",
            headers=_auth(raw_key),
            json={
                "session_id": "s1",
                "memory_type": "semantic",
                "content": f"token budget memory {index} " + ("word " * 40),
            },
        )
        assert created.status_code == 201

    search = client.get(
        "/memories/search",
        headers=_auth(raw_key),
        params={"q": "token budget memory", "session_id": "s1", "token_budget": 20},
    )
    assert search.status_code == 200
    assert 0 < len(search.json()["memories"]) < 3
