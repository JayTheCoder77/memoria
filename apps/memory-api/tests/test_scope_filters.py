from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from memory_api.db.deps import get_api_key_store, get_graph_store, get_kv_store, get_repository
from memory_api.db.repository import InMemoryMemoryRepository
from memory_api.main import app
from memory_api.services.api_keys import InMemoryApiKeyStore, generate_api_key
from memory_api.services.embedding import HashEmbedder, get_embedder
from memory_api.services.lexical import _LEXICAL_SQL
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
def graph() -> InMemoryGraphStore:
    return InMemoryGraphStore()


@pytest.fixture
def org_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def raw_key(keys: InMemoryApiKeyStore, org_id: uuid.UUID) -> str:
    raw = generate_api_key()
    keys.add(org_id=org_id, raw_key=raw)
    return raw


@pytest.fixture
def client(
    repo: InMemoryMemoryRepository,
    keys: InMemoryApiKeyStore,
    kv: InMemoryKVStore,
    graph: InMemoryGraphStore,
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


def _ids(payload: dict) -> set[str]:
    return {row["id"] for row in payload["memories"]}


def test_ava_cannot_see_sams_memory_kv_fact_or_graph_edge_unless_user_id_omitted(
    client: TestClient, raw_key: str
) -> None:
    content = "sam keeps the deploy notes in the org vault"
    created = client.post(
        "/memories",
        headers=_auth(raw_key),
        json={
            "session_id": "shared",
            "memory_type": "semantic",
            "content": content,
            "user_id": "sam",
            "kv_triples": [
                {"fact_type": "preference", "entity": "editor", "value": "helix"}
            ],
            "graph_triples": [
                {"subject": "sam", "relation": "uses", "object": "helix"}
            ],
        },
    )
    assert created.status_code == 201, created.text
    memory_id = created.json()["id"]

    hidden = client.get(
        "/memories/search",
        headers=_auth(raw_key),
        params={"q": content, "user_id": "ava"},
    )
    assert hidden.status_code == 200
    assert memory_id not in _ids(hidden.json())

    visible = client.get(
        "/memories/search",
        headers=_auth(raw_key),
        params={"q": content},
    )
    assert visible.status_code == 200
    assert memory_id in _ids(visible.json())

    hidden_list = client.get(
        "/memories",
        headers=_auth(raw_key),
        params={"user_id": "ava"},
    )
    assert memory_id not in _ids(hidden_list.json())
    open_list = client.get("/memories", headers=_auth(raw_key))
    assert memory_id in _ids(open_list.json())

    hidden_facts = client.get(
        "/kv-facts",
        headers=_auth(raw_key),
        params={"user_id": "ava"},
    )
    assert hidden_facts.status_code == 200
    assert hidden_facts.json()["facts"] == []

    open_facts = client.get("/kv-facts", headers=_auth(raw_key))
    assert any(row["entity"] == "editor" for row in open_facts.json()["facts"])

    hidden_edges = client.get(
        "/graph-edges",
        headers=_auth(raw_key),
        params={"user_id": "ava"},
    )
    assert hidden_edges.status_code == 200
    assert hidden_edges.json()["edges"] == []

    open_edges = client.get("/graph-edges", headers=_auth(raw_key))
    assert any(row["object"] == "helix" for row in open_edges.json()["edges"])


def test_passed_agent_id_must_match_and_omitted_agent_id_does_not_filter(
    client: TestClient, raw_key: str
) -> None:
    content = "the planner agent recorded the rollout window"
    created = client.post(
        "/memories",
        headers=_auth(raw_key),
        json={
            "session_id": "shared",
            "memory_type": "semantic",
            "content": content,
            "agent_id": "planner",
        },
    )
    assert created.status_code == 201, created.text
    memory_id = created.json()["id"]

    other_agent = client.get(
        "/memories/search",
        headers=_auth(raw_key),
        params={"q": content, "agent_id": "retriever"},
    )
    assert memory_id not in _ids(other_agent.json())

    same_agent = client.get(
        "/memories/search",
        headers=_auth(raw_key),
        params={"q": content, "agent_id": "planner"},
    )
    assert memory_id in _ids(same_agent.json())

    omitted = client.get(
        "/memories/search",
        headers=_auth(raw_key),
        params={"q": content},
    )
    assert memory_id in _ids(omitted.json())


def test_user_id_is_trimmed_and_rejects_more_than_128_characters(
    client: TestClient, raw_key: str
) -> None:
    content = "trimmed scope id still recalls"
    created = client.post(
        "/memories",
        headers=_auth(raw_key),
        json={
            "session_id": "shared",
            "memory_type": "semantic",
            "content": content,
            "user_id": "  sam  ",
        },
    )
    assert created.status_code == 201, created.text
    memory_id = created.json()["id"]

    trimmed = client.get(
        "/memories/search",
        headers=_auth(raw_key),
        params={"q": content, "user_id": "sam"},
    )
    assert memory_id in _ids(trimmed.json())

    too_long = client.post(
        "/memories",
        headers=_auth(raw_key),
        json={
            "session_id": "shared",
            "memory_type": "semantic",
            "content": "too long",
            "user_id": "a" * 129,
        },
    )
    assert too_long.status_code == 422


def test_two_users_can_store_the_same_kv_fact(
    client: TestClient, raw_key: str
) -> None:
    for user_id, value in (("ava", "vim"), ("sam", "helix")):
        created = client.post(
            "/memories",
            headers=_auth(raw_key),
            json={
                "session_id": "shared",
                "memory_type": "semantic",
                "content": f"{user_id} prefers {value}",
                "user_id": user_id,
                "kv_triples": [
                    {"fact_type": "preference", "entity": "editor", "value": value}
                ],
            },
        )
        assert created.status_code == 201, created.text

    facts = client.get("/kv-facts", headers=_auth(raw_key)).json()["facts"]
    values = {row["value"] for row in facts if row["entity"] == "editor"}
    assert values == {"vim", "helix"}

    ava = client.get(
        "/kv-facts",
        headers=_auth(raw_key),
        params={"user_id": "ava"},
    ).json()["facts"]
    assert {row["value"] for row in ava} == {"vim"}


def test_lexical_search_keeps_org_and_model_and_filters_user_and_agent() -> None:
    sql = str(_LEXICAL_SQL)
    assert "memories.org_id" in sql
    assert "memories.embedding_model" in sql
    assert "memories.user_id" in sql
    assert "memories.agent_id" in sql
