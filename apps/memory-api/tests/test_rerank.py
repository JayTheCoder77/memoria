from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from memory_api.db.deps import get_api_key_store, get_graph_store, get_kv_store, get_repository
from memory_api.db.repository import InMemoryMemoryRepository
from memory_api.main import app
from memory_api.services.api_keys import InMemoryApiKeyStore, generate_api_key
from memory_api.services.embedding import HashEmbedder, get_embedder
from memory_api.services.hybrid_search import RankedHit
from memory_api.stores.graph import InMemoryGraphStore
from memory_api.stores.kv import InMemoryKVStore


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
    app.dependency_overrides[get_kv_store] = lambda: InMemoryKVStore()
    app.dependency_overrides[get_graph_store] = lambda: InMemoryGraphStore()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _auth(raw_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {raw_key}"}


def _reverse(query: str, hits: list[RankedHit], *, limit: int) -> list[RankedHit]:
    return list(reversed(hits))[:limit]


def test_rerank_true_returns_400_when_reranker_is_not_configured(
    client: TestClient, raw_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("memory_api.config.settings.reranker", "")
    response = client.get(
        "/memories/search",
        headers=_auth(raw_key),
        params={"q": "rerank probe", "session_id": "s1", "rerank": True},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "reranker is not configured"


def test_search_returns_stub_rerank_that_reverses_hits(
    client: TestClient, raw_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    for index, importance in enumerate((0.1, 0.5, 0.95)):
        created = client.post(
            "/memories",
            headers=_auth(raw_key),
            json={
                "session_id": "s1",
                "memory_type": "semantic",
                "content": f"rerank probe {index} " + ("word " * 40),
                "importance": importance,
            },
        )
        assert created.status_code == 201

    baseline = client.get(
        "/memories/search",
        headers=_auth(raw_key),
        params={
            "q": "rerank probe",
            "session_id": "s1",
            "limit": 10,
            "token_budget": 10000,
        },
    )
    assert baseline.status_code == 200
    baseline_ids = [hit["id"] for hit in baseline.json()["memories"]]
    assert len(baseline_ids) >= 2
    assert baseline_ids != list(reversed(baseline_ids))

    monkeypatch.setattr(
        "memory_api.services.hybrid_search.rerank",
        _reverse,
        raising=False,
    )

    unchanged = client.get(
        "/memories/search",
        headers=_auth(raw_key),
        params={
            "q": "rerank probe",
            "session_id": "s1",
            "limit": 10,
            "token_budget": 10000,
            "rerank": False,
        },
    )
    assert unchanged.status_code == 200
    assert [hit["id"] for hit in unchanged.json()["memories"]] == baseline_ids

    reranked = client.get(
        "/memories/search",
        headers=_auth(raw_key),
        params={
            "q": "rerank probe",
            "session_id": "s1",
            "limit": 10,
            "token_budget": 10000,
            "rerank": True,
        },
    )
    assert reranked.status_code == 200
    assert [hit["id"] for hit in reranked.json()["memories"]] == list(reversed(baseline_ids))

    tight = client.get(
        "/memories/search",
        headers=_auth(raw_key),
        params={
            "q": "rerank probe",
            "session_id": "s1",
            "limit": 10,
            "token_budget": 1,
            "rerank": True,
        },
    )
    assert tight.status_code == 200
    assert [hit["id"] for hit in tight.json()["memories"]] == [baseline_ids[-1]]
