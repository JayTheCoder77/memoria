from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from memory_api.db.deps import get_api_key_store, get_event_store, get_repository
from memory_api.db.events import InMemoryEventStore
from memory_api.db.repository import InMemoryMemoryRepository
from memory_api.main import app
from memory_api.services.api_keys import InMemoryApiKeyStore, generate_api_key
from memory_api.services.embedding import HashEmbedder, get_embedder


@pytest.fixture
def events() -> InMemoryEventStore:
    return InMemoryEventStore()


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
def client(events: InMemoryEventStore, keys: InMemoryApiKeyStore) -> TestClient:
    app.dependency_overrides[get_event_store] = lambda: events
    app.dependency_overrides[get_repository] = lambda: InMemoryMemoryRepository()
    app.dependency_overrides[get_embedder] = lambda: HashEmbedder()
    app.dependency_overrides[get_api_key_store] = lambda: keys
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _auth(raw_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {raw_key}"}


def test_noisy_tool_is_skipped_without_a_row(
    client: TestClient, events: InMemoryEventStore, raw_key: str
) -> None:
    response = client.post(
        "/events",
        headers=_auth(raw_key),
        json={
            "session_id": "s1",
            "event_type": "tool_call",
            "payload": {"tool": "grep", "content": "noise"},
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "skipped"
    assert events.pending("s1") == []


def test_message_is_queued(
    client: TestClient, events: InMemoryEventStore, org_id: uuid.UUID, raw_key: str
) -> None:
    response = client.post(
        "/events",
        headers=_auth(raw_key),
        json={
            "session_id": "s1",
            "event_type": "message",
            "payload": {"content": "We prefer pytest."},
        },
    )
    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    pending = events.pending("s1")
    assert len(pending) == 1
    assert pending[0].org_id == org_id


def test_events_require_api_key(client: TestClient) -> None:
    response = client.post(
        "/events",
        json={"session_id": "s1", "event_type": "message", "payload": {}},
    )
    assert response.status_code == 401
