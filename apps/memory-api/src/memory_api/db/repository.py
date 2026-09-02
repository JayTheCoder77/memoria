from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from memory_api.db.models import Memory, MemoryType


class MemoryRepository(Protocol):
    def insert(
        self,
        *,
        org_id: uuid.UUID,
        session_id: str,
        memory_type: MemoryType,
        content: str,
        embedding: list[float],
        importance: float,
        source_metadata: dict,
    ) -> Memory: ...

    def search(
        self,
        *,
        org_id: uuid.UUID,
        query_embedding: list[float],
        session_id: str | None = None,
        limit: int = 10,
    ) -> list[tuple[Memory, float]]: ...

    def similar(
        self,
        *,
        org_id: uuid.UUID,
        query_embedding: list[float],
        session_id: str | None = None,
        limit: int = 10,
    ) -> list[tuple[Memory, float]]: ...

    def list(
        self,
        *,
        org_id: uuid.UUID,
        session_id: str | None = None,
        memory_type: MemoryType | None = None,
        q: str | None = None,
    ) -> list[Memory]: ...

    def get(self, *, org_id: uuid.UUID, memory_id: uuid.UUID) -> Memory | None: ...

    def delete(self, *, org_id: uuid.UUID, memory_id: uuid.UUID) -> bool: ...


def search_statement(
    *,
    org_id: uuid.UUID,
    query_embedding: list[float],
    session_id: str | None = None,
    limit: int = 10,
) -> Select:
    distance = Memory.embedding.cosine_distance(query_embedding)
    stmt = select(Memory, distance.label("distance")).where(Memory.org_id == org_id)
    if session_id is not None:
        stmt = stmt.where(Memory.session_id == session_id)
    return stmt.order_by(distance).limit(limit)


def _touch(memory: Memory) -> None:
    memory.access_count += 1
    memory.last_accessed_at = datetime.now(UTC)


def _cosine_distance(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    return 1.0 - dot


class PostgresMemoryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def insert(
        self,
        *,
        org_id: uuid.UUID,
        session_id: str,
        memory_type: MemoryType,
        content: str,
        embedding: list[float],
        importance: float,
        source_metadata: dict,
    ) -> Memory:
        memory = Memory(
            org_id=org_id,
            session_id=session_id,
            memory_type=memory_type,
            content=content,
            embedding=embedding,
            importance=importance,
            source_metadata=source_metadata,
        )
        self._session.add(memory)
        self._session.flush()
        return memory

    def search(
        self,
        *,
        org_id: uuid.UUID,
        query_embedding: list[float],
        session_id: str | None = None,
        limit: int = 10,
    ) -> list[tuple[Memory, float]]:
        rows = self._session.execute(
            search_statement(
                org_id=org_id,
                query_embedding=query_embedding,
                session_id=session_id,
                limit=limit,
            )
        ).all()
        results: list[tuple[Memory, float]] = []
        for memory, dist in rows:
            _touch(memory)
            results.append((memory, 1.0 - float(dist)))
        self._session.flush()
        return results

    def similar(
        self,
        *,
        org_id: uuid.UUID,
        query_embedding: list[float],
        session_id: str | None = None,
        limit: int = 10,
    ) -> list[tuple[Memory, float]]:
        rows = self._session.execute(
            search_statement(
                org_id=org_id,
                query_embedding=query_embedding,
                session_id=session_id,
                limit=limit,
            )
        ).all()
        return [(memory, 1.0 - float(dist)) for memory, dist in rows]

    def list(
        self,
        *,
        org_id: uuid.UUID,
        session_id: str | None = None,
        memory_type: MemoryType | None = None,
        q: str | None = None,
    ) -> list[Memory]:
        stmt = select(Memory).where(Memory.org_id == org_id)
        if session_id is not None:
            stmt = stmt.where(Memory.session_id == session_id)
        if memory_type is not None:
            stmt = stmt.where(Memory.memory_type == memory_type)
        if q:
            stmt = stmt.where(Memory.content.ilike(f"%{q}%"))
        stmt = stmt.order_by(Memory.created_at.desc())
        return list(self._session.scalars(stmt))

    def get(self, *, org_id: uuid.UUID, memory_id: uuid.UUID) -> Memory | None:
        return self._session.scalar(
            select(Memory).where(Memory.id == memory_id, Memory.org_id == org_id)
        )

    def delete(self, *, org_id: uuid.UUID, memory_id: uuid.UUID) -> bool:
        memory = self.get(org_id=org_id, memory_id=memory_id)
        if memory is None:
            return False
        self._session.delete(memory)
        self._session.flush()
        return True


class InMemoryMemoryRepository:
    def __init__(self) -> None:
        self._rows: list[Memory] = []

    def insert(
        self,
        *,
        org_id: uuid.UUID,
        session_id: str,
        memory_type: MemoryType,
        content: str,
        embedding: list[float],
        importance: float,
        source_metadata: dict,
    ) -> Memory:
        memory = Memory(
            id=uuid.uuid4(),
            org_id=org_id,
            session_id=session_id,
            memory_type=memory_type,
            content=content,
            embedding=list(embedding),
            importance=importance,
            source_metadata=source_metadata,
            access_count=0,
            created_at=datetime.now(UTC),
        )
        self._rows.append(memory)
        return memory

    def search(
        self,
        *,
        org_id: uuid.UUID,
        query_embedding: list[float],
        session_id: str | None = None,
        limit: int = 10,
    ) -> list[tuple[Memory, float]]:
        candidates = [row for row in self._rows if row.org_id == org_id]
        if session_id is not None:
            candidates = [row for row in candidates if row.session_id == session_id]
        ranked = sorted(
            candidates,
            key=lambda row: _cosine_distance(row.embedding, query_embedding),
        )[:limit]
        results: list[tuple[Memory, float]] = []
        for memory in ranked:
            _touch(memory)
            score = 1.0 - _cosine_distance(memory.embedding, query_embedding)
            results.append((memory, score))
        return results

    def similar(
        self,
        *,
        org_id: uuid.UUID,
        query_embedding: list[float],
        session_id: str | None = None,
        limit: int = 10,
    ) -> list[tuple[Memory, float]]:
        candidates = [row for row in self._rows if row.org_id == org_id]
        if session_id is not None:
            candidates = [row for row in candidates if row.session_id == session_id]
        ranked = sorted(
            candidates,
            key=lambda row: _cosine_distance(row.embedding, query_embedding),
        )[:limit]
        return [
            (memory, 1.0 - _cosine_distance(memory.embedding, query_embedding))
            for memory in ranked
        ]

    def list(
        self,
        *,
        org_id: uuid.UUID,
        session_id: str | None = None,
        memory_type: MemoryType | None = None,
        q: str | None = None,
    ) -> list[Memory]:
        rows = [row for row in self._rows if row.org_id == org_id]
        if session_id is not None:
            rows = [row for row in rows if row.session_id == session_id]
        if memory_type is not None:
            rows = [row for row in rows if row.memory_type == memory_type]
        if q:
            needle = q.lower()
            rows = [row for row in rows if needle in row.content.lower()]
        return sorted(rows, key=lambda row: row.created_at, reverse=True)

    def get(self, *, org_id: uuid.UUID, memory_id: uuid.UUID) -> Memory | None:
        for row in self._rows:
            if row.id == memory_id and row.org_id == org_id:
                return row
        return None

    def delete(self, *, org_id: uuid.UUID, memory_id: uuid.UUID) -> bool:
        memory = self.get(org_id=org_id, memory_id=memory_id)
        if memory is None:
            return False
        self._rows.remove(memory)
        return True
