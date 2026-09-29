from __future__ import annotations

import json
import uuid

import pytest
from fastapi.testclient import TestClient

from memory_api.db.deps import get_api_key_store, get_graph_store, get_kv_store, get_repository
from memory_api.db.repository import InMemoryMemoryRepository, search_statement
from memory_api.main import app
from memory_api.services.api_keys import InMemoryApiKeyStore, generate_api_key
from memory_api.services.embedding import EMBEDDING_DIM, HashEmbedder, get_embedder
from memory_api.stores.graph import InMemoryGraphStore
from memory_api.stores.kv import InMemoryKVStore


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
    app.dependency_overrides[get_kv_store] = lambda: InMemoryKVStore()
    app.dependency_overrides[get_graph_store] = lambda: InMemoryGraphStore()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _auth(raw_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {raw_key}"}


def test_dolphin_metadata_does_not_return_a_memory_tagged_cursor(
    client: TestClient, raw_key: str, org_id: uuid.UUID
) -> None:
    cursor = client.post(
        "/memories",
        headers=_auth(raw_key),
        json={
            "session_id": "meta-cursor",
            "memory_type": "semantic",
            "content": "cursor editor memory about shortcuts",
            "source_metadata": {"source": "cursor"},
        },
    )
    dolphin = client.post(
        "/memories",
        headers=_auth(raw_key),
        json={
            "session_id": "meta-dolphin",
            "memory_type": "semantic",
            "content": "dolphin bench memory about personas",
            "source_metadata": {"source": "dolphin"},
        },
    )
    assert cursor.status_code == 201
    assert dolphin.status_code == 201
    cursor_id = cursor.json()["id"]
    dolphin_id = dolphin.json()["id"]
    metadata = json.dumps({"source": "dolphin"})

    search = client.get(
        "/memories/search",
        headers=_auth(raw_key),
        params={"q": "memory", "metadata": metadata},
    )
    assert search.status_code == 200
    search_ids = {row["id"] for row in search.json()["memories"]}
    assert cursor_id not in search_ids
    assert dolphin_id in search_ids

    listed = client.get(
        "/memories",
        headers=_auth(raw_key),
        params={"metadata": metadata},
    )
    assert listed.status_code == 200
    listed_ids = {row["id"] for row in listed.json()["memories"]}
    assert cursor_id not in listed_ids
    assert dolphin_id in listed_ids

    stmt = search_statement(
        org_id=org_id,
        query_embedding=[0.0] * EMBEDDING_DIM,
        embedding_model="hash",
        metadata={"source": "dolphin"},
    )
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": False}))
    assert "memories.org_id" in compiled
    assert "memories.embedding_model" in compiled
    assert "source_metadata" in compiled
    assert "@>" in compiled


def test_array_containment_keeps_a_memory_tagged_with_a_superset(
    client: TestClient, raw_key: str
) -> None:
    superset = client.post(
        "/memories",
        headers=_auth(raw_key),
        json={
            "session_id": "meta-tags",
            "memory_type": "semantic",
            "content": "memory tagged with both labels",
            "source_metadata": {"tags": ["a", "b"]},
        },
    )
    other = client.post(
        "/memories",
        headers=_auth(raw_key),
        json={
            "session_id": "meta-tags",
            "memory_type": "semantic",
            "content": "memory tagged with a different label",
            "source_metadata": {"tags": ["c"]},
        },
    )
    assert superset.status_code == 201
    assert other.status_code == 201
    superset_id = superset.json()["id"]
    other_id = other.json()["id"]
    metadata = json.dumps({"tags": ["a"]})

    search = client.get(
        "/memories/search",
        headers=_auth(raw_key),
        params={"q": "memory", "metadata": metadata},
    )
    assert search.status_code == 200
    search_ids = {row["id"] for row in search.json()["memories"]}
    assert superset_id in search_ids
    assert other_id not in search_ids

    listed = client.get(
        "/memories",
        headers=_auth(raw_key),
        params={"metadata": metadata},
    )
    assert listed.status_code == 200
    listed_ids = {row["id"] for row in listed.json()["memories"]}
    assert superset_id in listed_ids
    assert other_id not in listed_ids
