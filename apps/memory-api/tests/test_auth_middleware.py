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


def test_write_without_bearer_is_unauthorized(client: TestClient) -> None:
    response = client.post(
        "/memories",
        json={"session_id": "s1", "memory_type": "semantic", "content": "no auth"},
    )
    assert response.status_code == 401


def test_write_uses_org_from_api_key(
    client: TestClient, org_id: uuid.UUID, raw_key: str
) -> None:
    response = client.post(
        "/memories",
        headers={"Authorization": f"Bearer {raw_key}"},
        json={"session_id": "s1", "memory_type": "semantic", "content": "from key"},
    )
    assert response.status_code == 201
    assert response.json()["org_id"] == str(org_id)


def test_revoked_key_cannot_search(
    client: TestClient, keys: InMemoryApiKeyStore, org_id: uuid.UUID
) -> None:
    raw = generate_api_key()
    record = keys.add(org_id=org_id, raw_key=raw)
    keys.revoke(record.id)
    response = client.get(
        "/memories/search",
        headers={"Authorization": f"Bearer {raw}"},
        params={"q": "anything", "session_id": "s1"},
    )
    assert response.status_code == 401
