from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from memory_api.db.models import KvFact
from memory_api.stores.types import KVFact


def normalize_kv_token(value: str) -> str:
    return value.strip().lower()


def _as_dataclass(row: KvFact) -> KVFact:
    return KVFact(
        org_id=row.org_id,
        memory_id=row.memory_id,
        fact_type=row.fact_type,
        entity=row.entity,
        value=row.value,
        importance=row.importance,
        user_key=row.user_key,
        id=row.id,
    )


class InMemoryKVStore:
    def __init__(self) -> None:
        self._rows: dict[tuple[uuid.UUID, str, str], KVFact] = {}

    def put(
        self,
        org_id: uuid.UUID,
        memory_id: uuid.UUID,
        fact_type: str,
        entity: str,
        *,
        value: str | None,
        importance: float,
        user_key: str | None = None,
    ) -> None:
        fact_type_n = normalize_kv_token(fact_type)
        entity_n = normalize_kv_token(entity)
        if not fact_type_n or not entity_n:
            return
        key = (org_id, fact_type_n, entity_n)
        existing = self._rows.get(key)
        self._rows[key] = KVFact(
            org_id=org_id,
            memory_id=memory_id,
            fact_type=fact_type_n,
            entity=entity_n,
            value=value,
            importance=importance,
            user_key=user_key,
            id=existing.id if existing is not None else uuid.uuid4(),
        )

    def get(self, org_id: uuid.UUID, fact_type: str, entity: str) -> KVFact | None:
        return self._rows.get(
            (org_id, normalize_kv_token(fact_type), normalize_kv_token(entity))
        )

    def search_keys(
        self, org_id: uuid.UUID, candidates: list[tuple[str, str]]
    ) -> list[KVFact]:
        found: list[KVFact] = []
        seen: set[tuple[str, str]] = set()
        for fact_type, entity in candidates:
            fact_type_n = normalize_kv_token(fact_type)
            entity_n = normalize_kv_token(entity)
            if (fact_type_n, entity_n) in seen:
                continue
            row = self.get(org_id, fact_type, entity)
            if row is None:
                continue
            seen.add((fact_type_n, entity_n))
            found.append(row)
        return found

    def by_org(self, org_id: uuid.UUID, *, user_key: str | None = None) -> list[KVFact]:
        rows = [row for row in self._rows.values() if row.org_id == org_id]
        if user_key is not None:
            rows = [row for row in rows if row.user_key == user_key]
        return rows


class PostgresKVStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def put(
        self,
        org_id: uuid.UUID,
        memory_id: uuid.UUID,
        fact_type: str,
        entity: str,
        *,
        value: str | None,
        importance: float,
        user_key: str | None = None,
    ) -> None:
        fact_type_n = normalize_kv_token(fact_type)
        entity_n = normalize_kv_token(entity)
        if not fact_type_n or not entity_n:
            return
        now = datetime.now(UTC)
        stmt = insert(KvFact).values(
            org_id=org_id,
            memory_id=memory_id,
            user_key=user_key,
            fact_type=fact_type_n,
            entity=entity_n,
            value=value,
            importance=importance,
            created_at=now,
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_kv_facts_org_type_entity",
            set_={
                "memory_id": memory_id,
                "value": value,
                "importance": importance,
                "user_key": user_key,
                "updated_at": now,
            },
        )
        self._session.execute(stmt)
        self._session.flush()

    def get(self, org_id: uuid.UUID, fact_type: str, entity: str) -> KVFact | None:
        row = self._session.scalar(
            select(KvFact).where(
                KvFact.org_id == org_id,
                KvFact.fact_type == normalize_kv_token(fact_type),
                KvFact.entity == normalize_kv_token(entity),
            )
        )
        return _as_dataclass(row) if row is not None else None

    def search_keys(
        self, org_id: uuid.UUID, candidates: list[tuple[str, str]]
    ) -> list[KVFact]:
        found: list[KVFact] = []
        seen: set[tuple[str, str]] = set()
        for fact_type, entity in candidates:
            fact_type_n = normalize_kv_token(fact_type)
            entity_n = normalize_kv_token(entity)
            if (fact_type_n, entity_n) in seen:
                continue
            row = self.get(org_id, fact_type, entity)
            if row is None:
                continue
            seen.add((fact_type_n, entity_n))
            found.append(row)
        return found

    def by_org(self, org_id: uuid.UUID, *, user_key: str | None = None) -> list[KVFact]:
        stmt = select(KvFact).where(KvFact.org_id == org_id)
        if user_key is not None:
            stmt = stmt.where(KvFact.user_key == user_key)
        return [_as_dataclass(row) for row in self._session.scalars(stmt)]
