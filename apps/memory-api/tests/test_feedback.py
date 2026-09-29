from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from memory_api.db.deps import get_api_key_store, get_graph_store, get_kv_store, get_repository
from memory_api.db.repository import InMemoryMemoryRepository
from memory_api.main import app
from memory_api.services.api_keys import InMemoryApiKeyStore, generate_api_key
from memory_api.services.embedding import HashEmbedder, get_embedder
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


def _remember(
    client: TestClient,
    raw_key: str,
    *,
    content: str,
    importance: float,
) -> dict:
    created = client.post(
        "/memories",
        headers=_auth(raw_key),
        json={
            "session_id": "feedback",
            "memory_type": "semantic",
            "content": content,
            "importance": importance,
        },
    )
    assert created.status_code == 201
    return created.json()


def test_useful_feedback_clamps_importance_at_1_0(
    client: TestClient, raw_key: str
) -> None:
    memory = _remember(
        client,
        raw_key,
        content="feedback clamp probe",
        importance=0.95,
    )

    voted = client.post(
        f"/memories/{memory['id']}/feedback",
        headers=_auth(raw_key),
        json={"useful": True},
    )

    assert voted.status_code == 200
    assert voted.json()["importance"] == 1.0


def test_not_useful_feedback_floors_importance_at_0(
    client: TestClient, raw_key: str
) -> None:
    memory = _remember(
        client,
        raw_key,
        content="feedback floor probe",
        importance=0.1,
    )

    voted = client.post(
        f"/memories/{memory['id']}/feedback",
        headers=_auth(raw_key),
        json={"useful": False},
    )

    assert voted.status_code == 200
    assert voted.json()["importance"] == 0.0


def test_second_vote_for_the_same_api_key_does_not_change_importance(
    client: TestClient, raw_key: str
) -> None:
    memory = _remember(
        client,
        raw_key,
        content="one vote probe",
        importance=0.5,
    )

    first = client.post(
        f"/memories/{memory['id']}/feedback",
        headers=_auth(raw_key),
        json={"useful": True},
    )
    assert first.status_code == 200
    assert first.json()["importance"] == 0.6

    second = client.post(
        f"/memories/{memory['id']}/feedback",
        headers=_auth(raw_key),
        json={"useful": True},
    )
    assert second.status_code == 409

    listed = client.get("/memories", headers=_auth(raw_key), params={"session_id": "feedback"})
    match = next(row for row in listed.json()["memories"] if row["id"] == memory["id"])
    assert match["importance"] == 0.6


def test_feedback_without_api_key_is_rejected(client: TestClient, raw_key: str) -> None:
    memory = _remember(
        client,
        raw_key,
        content="feedback requires a key",
        importance=0.4,
    )

    voted = client.post(
        f"/memories/{memory['id']}/feedback",
        json={"useful": True},
    )

    assert voted.status_code == 401
    listed = client.get("/memories", headers=_auth(raw_key), params={"session_id": "feedback"})
    match = next(row for row in listed.json()["memories"] if row["id"] == memory["id"])
    assert match["importance"] == 0.4


def test_duplicate_vote_409_is_distinct_from_a_missing_api_key(
    client: TestClient, raw_key: str, org_id: uuid.UUID
) -> None:
    from memory_api.auth import get_principal
    from memory_api.services.api_keys import Principal

    memory = _remember(
        client,
        raw_key,
        content="duplicate versus missing key",
        importance=0.5,
    )

    missing = client.post(
        f"/memories/{memory['id']}/feedback",
        json={"useful": True},
    )
    assert missing.status_code in {401, 403}
    assert missing.status_code != 409

    app.dependency_overrides[get_principal] = lambda: Principal(
        org_id=org_id, api_key_id=None
    )
    try:
        nameless = client.post(
            f"/memories/{memory['id']}/feedback",
            headers=_auth(raw_key),
            json={"useful": False},
        )
    finally:
        app.dependency_overrides.pop(get_principal, None)
    assert nameless.status_code in {401, 403}
    assert nameless.status_code != 409

    first = client.post(
        f"/memories/{memory['id']}/feedback",
        headers=_auth(raw_key),
        json={"useful": True},
    )
    assert first.status_code == 200
    assert first.json()["importance"] == 0.6

    second = client.post(
        f"/memories/{memory['id']}/feedback",
        headers=_auth(raw_key),
        json={"useful": False},
    )
    assert second.status_code == 409
    listed = client.get("/memories", headers=_auth(raw_key), params={"session_id": "feedback"})
    match = next(row for row in listed.json()["memories"] if row["id"] == memory["id"])
    assert match["importance"] == 0.6


def test_non_duplicate_integrity_error_is_not_a_second_vote() -> None:
    from sqlalchemy.exc import IntegrityError

    from memory_api.routers.feedback import PostgresFeedbackStore, is_duplicate_vote

    class _ForeignKeyOrig(Exception):
        sqlstate = "23503"

    foreign_key = IntegrityError("INSERT", {}, _ForeignKeyOrig())
    assert is_duplicate_vote(foreign_key) is False

    class _UniqueOrig(Exception):
        sqlstate = "23505"

    assert is_duplicate_vote(IntegrityError("INSERT", {}, _UniqueOrig())) is True

    class _Nested:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

    class _Session:
        def scalar(self, _stmt):
            return None

        def add(self, _row) -> None:
            return None

        def begin_nested(self):
            return _Nested()

        def flush(self) -> None:
            raise foreign_key

    with pytest.raises(IntegrityError):
        PostgresFeedbackStore(_Session()).record(
            org_id=uuid.uuid4(),
            memory_id=uuid.uuid4(),
            api_key_id=uuid.uuid4(),
            useful=True,
        )
