from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from memory_api.db.models import Org
from memory_api.db.session import SessionLocal, engine
from memory_api.main import app
from memory_api.services.embedding import HashEmbedder, get_embedder


def _postgres_available() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except OperationalError:
        return False


pytestmark = pytest.mark.skipif(not _postgres_available(), reason="Postgres is not running")


@pytest.fixture
def pg_client() -> TestClient:
    app.dependency_overrides[get_embedder] = lambda: HashEmbedder()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE memories, orgs CASCADE"))


@pytest.fixture
def org_id() -> str:
    org = Org(id=uuid.uuid4(), name="phase1-check", created_at=datetime.now(UTC))
    session = SessionLocal()
    try:
        session.add(org)
        session.commit()
        return str(org.id)
    finally:
        session.close()


def test_postgres_write_then_search_round_trip(pg_client: TestClient, org_id: str) -> None:
    content = "pgvector recall should return the inserted memory"
    created = pg_client.post(
        "/memories",
        json={
            "org_id": org_id,
            "session_id": "phase1",
            "memory_type": "semantic",
            "content": content,
            "importance": 0.8,
        },
    )
    assert created.status_code == 201, created.text
    memory_id = created.json()["id"]

    search = pg_client.get(
        "/memories/search",
        params={"org_id": org_id, "q": content, "session_id": "phase1"},
    )
    assert search.status_code == 200, search.text
    hits = search.json()["memories"]
    assert hits[0]["id"] == memory_id
    assert hits[0]["content"] == content
    assert hits[0]["score"] is not None


def test_postgres_search_isolates_tenants(pg_client: TestClient) -> None:
    session = SessionLocal()
    org_a = Org(name="org-a", created_at=datetime.now(UTC))
    org_b = Org(name="org-b", created_at=datetime.now(UTC))
    session.add_all([org_a, org_b])
    session.commit()
    a_id, b_id = str(org_a.id), str(org_b.id)
    session.close()

    content = "hashed api keys live in postgres"
    write_a = pg_client.post(
        "/memories",
        json={
            "org_id": a_id,
            "session_id": "s1",
            "memory_type": "procedural",
            "content": content,
        },
    )
    write_b = pg_client.post(
        "/memories",
        json={
            "org_id": b_id,
            "session_id": "s1",
            "memory_type": "procedural",
            "content": content,
        },
    )
    assert write_a.status_code == 201, write_a.text
    assert write_b.status_code == 201, write_b.text

    search_a = pg_client.get(
        "/memories/search",
        params={"org_id": a_id, "q": content, "session_id": "s1"},
    )
    ids = {hit["id"] for hit in search_a.json()["memories"]}
    assert write_a.json()["id"] in ids
    assert write_b.json()["id"] not in ids


def test_postgres_update_and_forget(pg_client: TestClient, org_id: str) -> None:
    created = pg_client.post(
        "/memories",
        json={
            "org_id": org_id,
            "session_id": "s1",
            "memory_type": "episodic",
            "content": "original postgres note",
        },
    )
    assert created.status_code == 201, created.text
    memory_id = created.json()["id"]

    updated = pg_client.patch(
        f"/memories/{memory_id}",
        params={"org_id": org_id},
        json={"content": "corrected postgres note", "importance": 0.3},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["content"] == "corrected postgres note"

    deleted = pg_client.delete(f"/memories/{memory_id}", params={"org_id": org_id})
    assert deleted.status_code == 204, deleted.text

    search = pg_client.get(
        "/memories/search",
        params={"org_id": org_id, "q": "corrected postgres note", "session_id": "s1"},
    )
    assert search.json()["memories"] == []
