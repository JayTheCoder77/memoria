from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from memory_api.db.models import ApiKey, Org, User
from memory_api.db.session import SessionLocal, engine
from memory_api.main import app
from memory_api.services.api_keys import generate_api_key, hash_api_key, key_last4
from memory_api.services.embedding import EMBEDDING_DIM, get_embedder


def _postgres_available() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except OperationalError:
        return False


pytestmark = pytest.mark.skipif(not _postgres_available(), reason="Postgres is not running")


def _auth(raw_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {raw_key}"}


def _issue_key(org: Org) -> str:
    raw = generate_api_key()
    user = User(
        org_id=org.id,
        google_id=f"google-{uuid.uuid4()}",
        email=f"{org.id}@example.test",
        name="test",
        created_at=datetime.now(UTC),
    )
    api_key = ApiKey(
        org_id=org.id,
        created_by=user,
        key_hash=hash_api_key(raw),
        key_last4=key_last4(raw),
        created_at=datetime.now(UTC),
    )
    session = SessionLocal()
    try:
        session.add_all([user, api_key])
        session.commit()
    finally:
        session.close()
    return raw


class _IgnoringEmbedder:
    """Returns a fixed vector and ignores the text, so similarity is not lexical."""

    model_name = "hash"

    def __init__(self, axis: int) -> None:
        vector = [0.0] * EMBEDDING_DIM
        vector[axis] = 1.0
        self._vector = vector

    def embed(self, text: str) -> list[float]:
        del text
        return list(self._vector)


@pytest.fixture
def pg_client() -> TestClient:
    app.dependency_overrides[get_embedder] = lambda: _IgnoringEmbedder(1)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE graph_edges, graph_nodes, kv_facts, memories, "
                "api_keys, users, event_buffer, orgs CASCADE"
            )
        )


@pytest.fixture
def org_and_key() -> tuple[str, str]:
    org = Org(id=uuid.uuid4(), name="lexical-check", created_at=datetime.now(UTC))
    session = SessionLocal()
    try:
        session.add(org)
        session.commit()
        session.refresh(org)
        org_id = str(org.id)
    finally:
        session.close()
    return org_id, _issue_key(org)


def test_lexical_search_returns_memory_when_vector_similarity_is_zero(
    pg_client: TestClient, org_and_key: tuple[str, str]
) -> None:
    _, raw_key = org_and_key
    created = pg_client.post(
        "/memories",
        headers=_auth(raw_key),
        json={
            "session_id": "s1",
            "memory_type": "semantic",
            "content": "billing entity is northwind",
        },
    )
    assert created.status_code == 201, created.text

    app.dependency_overrides[get_embedder] = lambda: _IgnoringEmbedder(0)
    search = pg_client.get(
        "/memories/search",
        headers=_auth(raw_key),
        params={"q": "northwind", "session_id": "s1", "explain": True},
    )
    assert search.status_code == 200, search.text
    hits = search.json()["memories"]
    assert hits, search.text
    hit = next(row for row in hits if row["id"] == created.json()["id"])
    assert hit["score_details"]["vector_similarity"] == 0.0
    assert hit["score_details"]["lexical"] > 0
