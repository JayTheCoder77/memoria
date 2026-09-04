from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from memory_api.db.models import ApiKey, Memory, MemoryType, Org, User
from memory_api.db.session import SessionLocal, engine
from memory_api.main import app
from memory_api.services.api_keys import generate_api_key, hash_api_key, key_last4
from memory_api.services.embedding import EMBEDDING_DIM, HashEmbedder, get_embedder
from memory_api.stores.kv import PostgresKVStore


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


@pytest.fixture
def pg_client() -> TestClient:
    app.dependency_overrides[get_embedder] = lambda: HashEmbedder()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE memories, api_keys, users, event_buffer, orgs CASCADE"))


@pytest.fixture
def org_and_key() -> tuple[str, str]:
    org = Org(id=uuid.uuid4(), name="phase1-check", created_at=datetime.now(UTC))
    session = SessionLocal()
    try:
        session.add(org)
        session.commit()
        session.refresh(org)
        org_id = str(org.id)
    finally:
        session.close()
    return org_id, _issue_key(org)


def test_postgres_write_then_search_round_trip(
    pg_client: TestClient, org_and_key: tuple[str, str]
) -> None:
    org_id, raw_key = org_and_key
    content = "pgvector recall should return the inserted memory"
    created = pg_client.post(
        "/memories",
        headers=_auth(raw_key),
        json={
            "session_id": "phase1",
            "memory_type": "semantic",
            "content": content,
            "importance": 0.8,
        },
    )
    assert created.status_code == 201, created.text
    memory_id = created.json()["id"]
    assert created.json()["org_id"] == org_id

    search = pg_client.get(
        "/memories/search",
        headers=_auth(raw_key),
        params={"q": content, "session_id": "phase1"},
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
    session.refresh(org_a)
    session.refresh(org_b)
    session.close()
    key_a = _issue_key(org_a)
    key_b = _issue_key(org_b)

    content = "hashed api keys live in postgres"
    write_a = pg_client.post(
        "/memories",
        headers=_auth(key_a),
        json={
            "session_id": "s1",
            "memory_type": "procedural",
            "content": content,
        },
    )
    write_b = pg_client.post(
        "/memories",
        headers=_auth(key_b),
        json={
            "session_id": "s1",
            "memory_type": "procedural",
            "content": content,
        },
    )
    assert write_a.status_code == 201, write_a.text
    assert write_b.status_code == 201, write_b.text

    search_a = pg_client.get(
        "/memories/search",
        headers=_auth(key_a),
        params={"q": content, "session_id": "s1"},
    )
    ids = {hit["id"] for hit in search_a.json()["memories"]}
    assert write_a.json()["id"] in ids
    assert write_b.json()["id"] not in ids


def test_postgres_kv_store_round_trip_and_tenant_isolation() -> None:
    session = SessionLocal()
    try:
        org_a = Org(id=uuid.uuid4(), name="a", created_at=datetime.now(UTC))
        org_b = Org(id=uuid.uuid4(), name="b", created_at=datetime.now(UTC))
        session.add_all([org_a, org_b])
        session.flush()
        mem_a = Memory(
            org_id=org_a.id,
            session_id="s1",
            memory_type=MemoryType.semantic,
            content="a",
            embedding=[0.0] * EMBEDDING_DIM,
            importance=0.5,
            source_metadata={},
        )
        mem_b = Memory(
            org_id=org_b.id,
            session_id="s1",
            memory_type=MemoryType.semantic,
            content="b",
            embedding=[0.0] * EMBEDDING_DIM,
            importance=0.5,
            source_metadata={},
        )
        session.add_all([mem_a, mem_b])
        session.flush()
        store = PostgresKVStore(session)
        store.put(org_a.id, mem_a.id, "preference", "typescript", value="ts", importance=0.8)
        store.put(org_b.id, mem_b.id, "preference", "typescript", value="no", importance=0.1)
        hit = store.get(org_a.id, "preference", "typescript")
        assert hit is not None
        assert hit.memory_id == mem_a.id
        assert hit.value == "ts"
        keys = store.search_keys(org_a.id, [("preference", "typescript")])
        assert len(keys) == 1
        assert keys[0].memory_id == mem_a.id
        session.rollback()
    finally:
        session.close()


def test_postgres_update_and_forget(
    pg_client: TestClient, org_and_key: tuple[str, str]
) -> None:
    _, raw_key = org_and_key
    created = pg_client.post(
        "/memories",
        headers=_auth(raw_key),
        json={
            "session_id": "s1",
            "memory_type": "episodic",
            "content": "original postgres note",
        },
    )
    assert created.status_code == 201, created.text
    memory_id = created.json()["id"]

    updated = pg_client.patch(
        f"/memories/{memory_id}",
        headers=_auth(raw_key),
        json={"content": "corrected postgres note", "importance": 0.3},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["content"] == "corrected postgres note"

    deleted = pg_client.delete(f"/memories/{memory_id}", headers=_auth(raw_key))
    assert deleted.status_code == 204, deleted.text

    search = pg_client.get(
        "/memories/search",
        headers=_auth(raw_key),
        params={"q": "corrected postgres note", "session_id": "s1"},
    )
    assert search.json()["memories"] == []
