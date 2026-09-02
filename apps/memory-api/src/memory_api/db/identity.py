from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from memory_api.db.models import ApiKey, Org, User
from memory_api.services.api_keys import generate_api_key, hash_api_key, key_last4
from memory_api.services.google_auth import GoogleClaims


class IdentityRepository(Protocol):
    def find_or_create_google_user(self, claims: GoogleClaims) -> User: ...

    def get_user(self, user_id: uuid.UUID) -> User | None: ...

    def create_api_key(self, user: User) -> tuple[ApiKey, str]: ...

    def list_api_keys(self, org_id: uuid.UUID) -> list[ApiKey]: ...

    def revoke_api_key(self, *, org_id: uuid.UUID, key_id: uuid.UUID) -> ApiKey | None: ...


class InMemoryIdentityRepository:
    def __init__(self) -> None:
        self._users_by_google: dict[str, User] = {}
        self._users_by_id: dict[uuid.UUID, User] = {}
        self._keys: list[ApiKey] = []

    def find_or_create_google_user(self, claims: GoogleClaims) -> User:
        existing = self._users_by_google.get(claims.google_id)
        if existing is not None:
            return existing
        org = Org(id=uuid.uuid4(), name=f"{claims.name}'s org", created_at=datetime.now(UTC))
        user = User(
            id=uuid.uuid4(),
            org_id=org.id,
            google_id=claims.google_id,
            email=claims.email,
            name=claims.name,
            created_at=datetime.now(UTC),
        )
        user.org = org
        self._users_by_google[claims.google_id] = user
        self._users_by_id[user.id] = user
        return user

    def get_user(self, user_id: uuid.UUID) -> User | None:
        return self._users_by_id.get(user_id)

    def create_api_key(self, user: User) -> tuple[ApiKey, str]:
        raw = generate_api_key()
        key = ApiKey(
            id=uuid.uuid4(),
            org_id=user.org_id,
            created_by_user_id=user.id,
            key_hash=hash_api_key(raw),
            key_last4=key_last4(raw),
            created_at=datetime.now(UTC),
        )
        self._keys.append(key)
        return key, raw

    def list_api_keys(self, org_id: uuid.UUID) -> list[ApiKey]:
        return [key for key in self._keys if key.org_id == org_id]

    def revoke_api_key(self, *, org_id: uuid.UUID, key_id: uuid.UUID) -> ApiKey | None:
        for key in self._keys:
            if key.id == key_id and key.org_id == org_id:
                key.revoked_at = datetime.now(UTC)
                return key
        return None


class PostgresIdentityRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def find_or_create_google_user(self, claims: GoogleClaims) -> User:
        user = self._session.scalar(select(User).where(User.google_id == claims.google_id))
        if user is not None:
            return user
        org = Org(name=f"{claims.name}'s org")
        user = User(
            org=org,
            google_id=claims.google_id,
            email=claims.email,
            name=claims.name,
        )
        self._session.add_all([org, user])
        self._session.flush()
        return user

    def get_user(self, user_id: uuid.UUID) -> User | None:
        return self._session.get(User, user_id)

    def create_api_key(self, user: User) -> tuple[ApiKey, str]:
        raw = generate_api_key()
        key = ApiKey(
            org_id=user.org_id,
            created_by_user_id=user.id,
            key_hash=hash_api_key(raw),
            key_last4=key_last4(raw),
        )
        self._session.add(key)
        self._session.flush()
        return key, raw

    def list_api_keys(self, org_id: uuid.UUID) -> list[ApiKey]:
        return list(self._session.scalars(select(ApiKey).where(ApiKey.org_id == org_id)))

    def revoke_api_key(self, *, org_id: uuid.UUID, key_id: uuid.UUID) -> ApiKey | None:
        key = self._session.scalar(
            select(ApiKey).where(ApiKey.id == key_id, ApiKey.org_id == org_id)
        )
        if key is None:
            return None
        key.revoked_at = datetime.now(UTC)
        self._session.flush()
        return key
