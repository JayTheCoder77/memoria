from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

KEY_PREFIX = "mem_"


class AuthError(Exception):
    pass


@dataclass(frozen=True)
class Principal:
    org_id: uuid.UUID
    api_key_id: uuid.UUID


@dataclass
class ApiKeyRecord:
    id: uuid.UUID
    org_id: uuid.UUID
    key_hash: str
    revoked_at: datetime | None = None
    last_used_at: datetime | None = None


class ApiKeyStore(Protocol):
    def find_by_hash(self, key_hash: str) -> ApiKeyRecord | None: ...

    def mark_used(self, key_id: uuid.UUID) -> None: ...


class InMemoryApiKeyStore:
    def __init__(self) -> None:
        self._keys: dict[uuid.UUID, ApiKeyRecord] = {}

    def add(self, org_id: uuid.UUID, raw_key: str) -> ApiKeyRecord:
        record = ApiKeyRecord(
            id=uuid.uuid4(),
            org_id=org_id,
            key_hash=hash_api_key(raw_key),
        )
        self._keys[record.id] = record
        return record

    def revoke(self, key_id: uuid.UUID) -> None:
        self._keys[key_id].revoked_at = datetime.now(UTC)

    def last_used_at(self, key_id: uuid.UUID) -> datetime | None:
        return self._keys[key_id].last_used_at

    def find_by_hash(self, key_hash: str) -> ApiKeyRecord | None:
        for record in self._keys.values():
            if record.key_hash == key_hash:
                return record
        return None

    def mark_used(self, key_id: uuid.UUID) -> None:
        self._keys[key_id].last_used_at = datetime.now(UTC)


class PostgresApiKeyStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def find_by_hash(self, key_hash: str) -> ApiKeyRecord | None:
        from memory_api.db.models import ApiKey

        row = self._session.scalar(select(ApiKey).where(ApiKey.key_hash == key_hash))
        if row is None:
            return None
        return ApiKeyRecord(
            id=row.id,
            org_id=row.org_id,
            key_hash=row.key_hash,
            revoked_at=row.revoked_at,
            last_used_at=row.last_used_at,
        )

    def mark_used(self, key_id: uuid.UUID) -> None:
        from memory_api.db.models import ApiKey

        row = self._session.get(ApiKey, key_id)
        if row is not None:
            row.last_used_at = datetime.now(UTC)


def generate_api_key() -> str:
    return f"{KEY_PREFIX}{secrets.token_urlsafe(32)}"


def hash_api_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def key_last4(raw: str) -> str:
    return raw[-4:]


def authenticate_bearer(authorization: str | None, store: ApiKeyStore) -> Principal:
    if authorization is None or not authorization.startswith("Bearer "):
        raise AuthError("missing bearer token")
    raw = authorization.removeprefix("Bearer ").strip()
    if not raw:
        raise AuthError("missing bearer token")
    record = store.find_by_hash(hash_api_key(raw))
    if record is None or record.revoked_at is not None:
        raise AuthError("invalid api key")
    store.mark_used(record.id)
    return Principal(org_id=record.org_id, api_key_id=record.id)
