from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from memory_api.db.models import KvFact, Memory
from memory_api.db.models import KvFactHistory as KvFactHistoryRow
from memory_api.services.entities import normalize_entity
from memory_api.services.scope import exposed_scope_id, scope_matches, stored_scope_id
from memory_api.stores.types import KVFact, KVFactHistory


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
        user_id=exposed_scope_id(row.user_id),
        agent_id=row.agent_id,
    )


def _history_from_row(row: KvFactHistoryRow) -> KVFactHistory:
    return KVFactHistory(
        id=row.id,
        org_id=row.org_id,
        user_id=row.user_id,
        fact_type=row.fact_type,
        entity=row.entity,
        value=row.value,
        memory_id=row.memory_id,
        valid_from=row.valid_from,
        valid_to=row.valid_to,
    )


class InMemoryKVStore:
    def __init__(self) -> None:
        self._rows: dict[tuple[uuid.UUID, str, str, str], KVFact] = {}
        self._history: list[KVFactHistory] = []

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
        user_id: str | None = None,
        agent_id: str | None = None,
    ) -> None:
        fact_type_n = normalize_kv_token(fact_type)
        entity_n = normalize_entity(entity)
        if not fact_type_n or not entity_n:
            return
        db_user = stored_scope_id(user_id)
        key = (org_id, db_user, fact_type_n, entity_n)
        existing = self._rows.get(key)
        if existing is None or existing.value != value:
            self._version_value(
                org_id=org_id,
                user_id=db_user,
                fact_type=fact_type_n,
                entity=entity_n,
                value=value,
                memory_id=memory_id,
            )
        self._rows[key] = KVFact(
            org_id=org_id,
            memory_id=memory_id,
            fact_type=fact_type_n,
            entity=entity_n,
            value=value,
            importance=importance,
            user_key=user_key,
            id=existing.id if existing is not None else uuid.uuid4(),
            user_id=user_id,
            agent_id=agent_id,
        )

    def get(
        self,
        org_id: uuid.UUID,
        fact_type: str,
        entity: str,
        *,
        user_id: str | None = None,
        agent_id: str | None = None,
    ) -> KVFact | None:
        fact_type_n = normalize_kv_token(fact_type)
        entity_n = normalize_entity(entity)
        if user_id is not None:
            row = self._rows.get((org_id, stored_scope_id(user_id), fact_type_n, entity_n))
            if row is None or not scope_matches(
                row.user_id, row.agent_id, user_id=user_id, agent_id=agent_id
            ):
                return None
            return row
        for row in self._rows.values():
            if (
                row.org_id == org_id
                and row.fact_type == fact_type_n
                and row.entity == entity_n
                and scope_matches(
                    row.user_id, row.agent_id, user_id=user_id, agent_id=agent_id
                )
            ):
                return row
        return None

    def search_keys(
        self,
        org_id: uuid.UUID,
        candidates: list[tuple[str, str]],
        *,
        user_id: str | None = None,
        agent_id: str | None = None,
    ) -> list[KVFact]:
        found: list[KVFact] = []
        seen: set[tuple[str, str, str]] = set()
        for fact_type, entity in candidates:
            fact_type_n = normalize_kv_token(fact_type)
            entity_n = normalize_entity(entity)
            for row in self._rows.values():
                if row.org_id != org_id or row.fact_type != fact_type_n or row.entity != entity_n:
                    continue
                if not scope_matches(
                    row.user_id, row.agent_id, user_id=user_id, agent_id=agent_id
                ):
                    continue
                key = (row.user_id or "", fact_type_n, entity_n)
                if key in seen:
                    continue
                seen.add(key)
                found.append(row)
        return found

    def by_org(
        self,
        org_id: uuid.UUID,
        *,
        user_key: str | None = None,
        user_id: str | None = None,
        agent_id: str | None = None,
    ) -> list[KVFact]:
        rows = [
            row
            for row in self._rows.values()
            if row.org_id == org_id
            and scope_matches(row.user_id, row.agent_id, user_id=user_id, agent_id=agent_id)
        ]
        if user_key is not None:
            rows = [row for row in rows if row.user_key == user_key]
        return rows

    def history(
        self,
        org_id: uuid.UUID,
        *,
        user_id: str | None = None,
        fact_type: str | None = None,
        entity: str | None = None,
    ) -> list[KVFactHistory]:
        rows = [row for row in self._history if row.org_id == org_id]
        if user_id is not None:
            stored = stored_scope_id(user_id)
            rows = [row for row in rows if row.user_id == stored]
        if fact_type is not None:
            fact_type_n = normalize_kv_token(fact_type)
            rows = [row for row in rows if row.fact_type == fact_type_n]
        if entity is not None:
            entity_n = normalize_entity(entity)
            rows = [row for row in rows if row.entity == entity_n]
        return rows

    def _version_value(
        self,
        *,
        org_id: uuid.UUID,
        user_id: str,
        fact_type: str,
        entity: str,
        value: str | None,
        memory_id: uuid.UUID,
    ) -> None:
        now = datetime.now(UTC)
        updated: list[KVFactHistory] = []
        for row in self._history:
            if (
                row.valid_to is None
                and row.org_id == org_id
                and row.user_id == user_id
                and row.fact_type == fact_type
                and row.entity == entity
            ):
                updated.append(replace(row, valid_to=now))
            else:
                updated.append(row)
        updated.append(
            KVFactHistory(
                id=uuid.uuid4(),
                org_id=org_id,
                user_id=user_id,
                fact_type=fact_type,
                entity=entity,
                value=value,
                memory_id=memory_id,
                valid_from=now,
                valid_to=None,
            )
        )
        self._history = updated


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
        user_id: str | None = None,
        agent_id: str | None = None,
    ) -> None:
        fact_type_n = normalize_kv_token(fact_type)
        entity_n = normalize_entity(entity)
        if not fact_type_n or not entity_n:
            return
        db_user = stored_scope_id(user_id)
        memory_exists = self._session.scalar(
            select(Memory.id).where(
                Memory.id == memory_id,
                Memory.org_id == org_id,
            )
        )
        if memory_exists is None:
            return
        existing = self._session.scalar(
            select(KvFact).where(
                KvFact.org_id == org_id,
                KvFact.user_id == db_user,
                KvFact.fact_type == fact_type_n,
                KvFact.entity == entity_n,
            )
        )
        now = datetime.now(UTC)
        if existing is None or existing.value != value:
            self._version_value(
                org_id=org_id,
                user_id=db_user,
                fact_type=fact_type_n,
                entity=entity_n,
                value=value,
                memory_id=memory_id,
                now=now,
            )
        stmt = insert(KvFact).values(
            org_id=org_id,
            memory_id=memory_id,
            user_key=user_key,
            user_id=db_user,
            agent_id=agent_id,
            fact_type=fact_type_n,
            entity=entity_n,
            value=value,
            importance=importance,
            created_at=now,
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_kv_facts_org_user_type_entity",
            set_={
                "memory_id": memory_id,
                "value": value,
                "importance": importance,
                "user_key": user_key,
                "agent_id": agent_id,
                "updated_at": now,
            },
        )
        self._session.execute(stmt)
        self._session.flush()
        for obj in self._session:
            if (
                isinstance(obj, KvFact)
                and obj.org_id == org_id
                and obj.user_id == db_user
                and obj.fact_type == fact_type_n
                and obj.entity == entity_n
            ):
                self._session.expire(obj)

    def get(
        self,
        org_id: uuid.UUID,
        fact_type: str,
        entity: str,
        *,
        user_id: str | None = None,
        agent_id: str | None = None,
    ) -> KVFact | None:
        stmt = select(KvFact).where(
            KvFact.org_id == org_id,
            KvFact.fact_type == normalize_kv_token(fact_type),
            KvFact.entity == normalize_entity(entity),
        )
        if user_id is not None:
            stmt = stmt.where(KvFact.user_id == user_id)
        if agent_id is not None:
            stmt = stmt.where(KvFact.agent_id == agent_id)
        row = self._session.scalars(stmt).first()
        return _as_dataclass(row) if row is not None else None

    def search_keys(
        self,
        org_id: uuid.UUID,
        candidates: list[tuple[str, str]],
        *,
        user_id: str | None = None,
        agent_id: str | None = None,
    ) -> list[KVFact]:
        if not candidates:
            return []
        stmt = select(KvFact).where(KvFact.org_id == org_id)
        if user_id is not None:
            stmt = stmt.where(KvFact.user_id == user_id)
        if agent_id is not None:
            stmt = stmt.where(KvFact.agent_id == agent_id)
        wanted = {
            (normalize_kv_token(fact_type), normalize_entity(entity))
            for fact_type, entity in candidates
        }
        found: list[KVFact] = []
        seen: set[tuple[str, str, str]] = set()
        for row in self._session.scalars(stmt):
            if (row.fact_type, row.entity) not in wanted:
                continue
            key = (row.user_id, row.fact_type, row.entity)
            if key in seen:
                continue
            seen.add(key)
            found.append(_as_dataclass(row))
        return found

    def by_org(
        self,
        org_id: uuid.UUID,
        *,
        user_key: str | None = None,
        user_id: str | None = None,
        agent_id: str | None = None,
    ) -> list[KVFact]:
        stmt = select(KvFact).where(KvFact.org_id == org_id)
        if user_key is not None:
            stmt = stmt.where(KvFact.user_key == user_key)
        if user_id is not None:
            stmt = stmt.where(KvFact.user_id == user_id)
        if agent_id is not None:
            stmt = stmt.where(KvFact.agent_id == agent_id)
        return [_as_dataclass(row) for row in self._session.scalars(stmt)]

    def history(
        self,
        org_id: uuid.UUID,
        *,
        user_id: str | None = None,
        fact_type: str | None = None,
        entity: str | None = None,
    ) -> list[KVFactHistory]:
        stmt = select(KvFactHistoryRow).where(KvFactHistoryRow.org_id == org_id)
        if user_id is not None:
            stmt = stmt.where(KvFactHistoryRow.user_id == stored_scope_id(user_id))
        if fact_type is not None:
            stmt = stmt.where(KvFactHistoryRow.fact_type == normalize_kv_token(fact_type))
        if entity is not None:
            stmt = stmt.where(KvFactHistoryRow.entity == normalize_entity(entity))
        return [_history_from_row(row) for row in self._session.scalars(stmt)]

    def _version_value(
        self,
        *,
        org_id: uuid.UUID,
        user_id: str,
        fact_type: str,
        entity: str,
        value: str | None,
        memory_id: uuid.UUID,
        now: datetime,
    ) -> None:
        open_rows = self._session.scalars(
            select(KvFactHistoryRow).where(
                KvFactHistoryRow.org_id == org_id,
                KvFactHistoryRow.user_id == user_id,
                KvFactHistoryRow.fact_type == fact_type,
                KvFactHistoryRow.entity == entity,
                KvFactHistoryRow.valid_to.is_(None),
            )
        ).all()
        for row in open_rows:
            row.valid_to = now
        if open_rows:
            self._session.flush()
        self._session.add(
            KvFactHistoryRow(
                org_id=org_id,
                user_id=user_id,
                fact_type=fact_type,
                entity=entity,
                value=value,
                memory_id=memory_id,
                valid_from=now,
                valid_to=None,
            )
        )
        self._session.flush()
