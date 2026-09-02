from __future__ import annotations

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError

from memory_api.cli import issue_api_key
from memory_api.db.models import ApiKey
from memory_api.db.session import SessionLocal, engine
from memory_api.services.api_keys import PostgresApiKeyStore, authenticate_bearer, hash_api_key


def _postgres_available() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except OperationalError:
        return False


pytestmark = pytest.mark.skipif(not _postgres_available(), reason="Postgres is not running")


def test_issue_api_key_is_hashed_and_authenticates() -> None:
    session = SessionLocal()
    try:
        org, raw = issue_api_key(session, org_name="cli-org")
        stored = session.scalar(select(ApiKey))
        assert stored is not None
        assert stored.key_hash == hash_api_key(raw)
        assert stored.org_id == org.id
        principal = authenticate_bearer(f"Bearer {raw}", PostgresApiKeyStore(session))
        assert principal.org_id == org.id
        session.commit()
    finally:
        session.close()
        with engine.begin() as connection:
            connection.execute(
                text("TRUNCATE memories, api_keys, users, event_buffer, orgs CASCADE")
            )
