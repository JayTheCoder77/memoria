from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from memory_api.db.deps import get_api_key_store, get_rate_limiter, get_repository
from memory_api.db.repository import InMemoryMemoryRepository
from memory_api.main import app
from memory_api.services.api_keys import InMemoryApiKeyStore, generate_api_key
from memory_api.services.embedding import HashEmbedder, get_embedder
from memory_api.services.rate_limit import SlidingWindowRateLimiter


@pytest.fixture
def client() -> TestClient:
    keys = InMemoryApiKeyStore()
    raw = generate_api_key()
    keys.add(org_id=uuid.uuid4(), raw_key=raw)
    limiter = SlidingWindowRateLimiter(limit=2, window_seconds=60)
    app.dependency_overrides[get_repository] = lambda: InMemoryMemoryRepository()
    app.dependency_overrides[get_embedder] = lambda: HashEmbedder()
    app.dependency_overrides[get_api_key_store] = lambda: keys
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    with TestClient(app) as test_client:
        test_client.headers["Authorization"] = f"Bearer {raw}"
        yield test_client
    app.dependency_overrides.clear()


def test_third_request_in_window_is_rate_limited(client: TestClient) -> None:
    payload = {"session_id": "s1", "memory_type": "semantic", "content": "rate limit me"}
    assert client.post("/memories", json=payload).status_code == 201
    assert client.post("/memories", json=payload).status_code == 201
    blocked = client.post("/memories", json=payload)
    assert blocked.status_code == 429
