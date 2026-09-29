from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from memory_api.db.models import EventBuffer, EventStatus


class EventStore(Protocol):
    def enqueue(
        self,
        *,
        org_id: uuid.UUID,
        session_id: str,
        event_type: str,
        payload: dict,
    ) -> EventBuffer: ...

    def pending(self, session_id: str) -> list[EventBuffer]: ...

    def pending_count(self, *, org_id: uuid.UUID, session_id: str) -> int: ...

    def failed_count(self, *, org_id: uuid.UUID, session_id: str) -> int: ...

    def claim_ready(
        self, batch_size: int, *, group_window_seconds: int = 120
    ) -> list[EventBuffer]: ...

    def mark_processed(self, events: list[EventBuffer]) -> None: ...

    def mark_failed(self, events: list[EventBuffer]) -> None: ...


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _group_ready(batch: list[EventBuffer], *, batch_size: int, group_window_seconds: int) -> bool:
    if any(item.event_type == "session_end" for item in batch):
        return True
    if len(batch) >= batch_size:
        return True
    newest = max(_aware(item.created_at) for item in batch)
    return (_utcnow() - newest).total_seconds() > group_window_seconds


class InMemoryEventStore:
    def __init__(self) -> None:
        self._rows: list[EventBuffer] = []

    def enqueue(
        self,
        *,
        org_id: uuid.UUID,
        session_id: str,
        event_type: str,
        payload: dict,
    ) -> EventBuffer:
        row = EventBuffer(
            id=uuid.uuid4(),
            org_id=org_id,
            session_id=session_id,
            event_type=event_type,
            payload=payload,
            status=EventStatus.pending,
            created_at=_utcnow(),
        )
        self._rows.append(row)
        return row

    def pending(self, session_id: str) -> list[EventBuffer]:
        return [
            row
            for row in self._rows
            if row.session_id == session_id and row.status == EventStatus.pending
        ]

    def pending_count(self, *, org_id: uuid.UUID, session_id: str) -> int:
        open_statuses = {EventStatus.pending, EventStatus.processing}
        return sum(
            1
            for row in self._rows
            if row.org_id == org_id
            and row.session_id == session_id
            and row.status in open_statuses
        )

    def failed_count(self, *, org_id: uuid.UUID, session_id: str) -> int:
        return sum(
            1
            for row in self._rows
            if row.org_id == org_id
            and row.session_id == session_id
            and row.status == EventStatus.failed
        )

    def claim_ready(self, batch_size: int, *, group_window_seconds: int = 120) -> list[EventBuffer]:
        grouped: dict[tuple[uuid.UUID, str], list[EventBuffer]] = {}
        for row in sorted(self._rows, key=lambda item: item.created_at):
            if row.status != EventStatus.pending:
                continue
            grouped.setdefault((row.org_id, row.session_id), []).append(row)
        claimed: list[EventBuffer] = []
        for batch in grouped.values():
            if not _group_ready(
                batch, batch_size=batch_size, group_window_seconds=group_window_seconds
            ):
                continue
            for item in batch:
                item.status = EventStatus.processing
            claimed.extend(batch)
        return claimed

    def mark_processed(self, events: list[EventBuffer]) -> None:
        now = _utcnow()
        for row in events:
            row.status = EventStatus.processed
            row.processed_at = now

    def mark_failed(self, events: list[EventBuffer]) -> None:
        now = _utcnow()
        for row in events:
            row.status = EventStatus.failed
            row.processed_at = now


class PostgresEventStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def enqueue(
        self,
        *,
        org_id: uuid.UUID,
        session_id: str,
        event_type: str,
        payload: dict,
    ) -> EventBuffer:
        row = EventBuffer(
            org_id=org_id,
            session_id=session_id,
            event_type=event_type,
            payload=payload,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def pending(self, session_id: str) -> list[EventBuffer]:
        return list(
            self._session.scalars(
                select(EventBuffer)
                .where(
                    EventBuffer.session_id == session_id,
                    EventBuffer.status == EventStatus.pending,
                )
                .order_by(EventBuffer.created_at)
            )
        )

    def pending_count(self, *, org_id: uuid.UUID, session_id: str) -> int:
        return self._status_count(
            org_id=org_id,
            session_id=session_id,
            statuses=(EventStatus.pending, EventStatus.processing),
        )

    def failed_count(self, *, org_id: uuid.UUID, session_id: str) -> int:
        return self._status_count(
            org_id=org_id,
            session_id=session_id,
            statuses=(EventStatus.failed,),
        )

    def _status_count(
        self,
        *,
        org_id: uuid.UUID,
        session_id: str,
        statuses: tuple[EventStatus, ...],
    ) -> int:
        count = self._session.scalar(
            select(func.count())
            .select_from(EventBuffer)
            .where(
                EventBuffer.org_id == org_id,
                EventBuffer.session_id == session_id,
                EventBuffer.status.in_(statuses),
            )
        )
        return int(count or 0)

    def claim_ready(self, batch_size: int, *, group_window_seconds: int = 120) -> list[EventBuffer]:
        pending = list(
            self._session.scalars(
                select(EventBuffer)
                .where(EventBuffer.status == EventStatus.pending)
                .order_by(EventBuffer.created_at)
                .with_for_update(skip_locked=True)
            )
        )
        grouped: dict[tuple[uuid.UUID, str], list[EventBuffer]] = {}
        for row in pending:
            grouped.setdefault((row.org_id, row.session_id), []).append(row)
        claimed: list[EventBuffer] = []
        for batch in grouped.values():
            if not _group_ready(
                batch, batch_size=batch_size, group_window_seconds=group_window_seconds
            ):
                continue
            for item in batch:
                item.status = EventStatus.processing
            claimed.extend(batch)
        self._session.flush()
        return claimed

    def mark_processed(self, events: list[EventBuffer]) -> None:
        now = _utcnow()
        for row in events:
            row.status = EventStatus.processed
            row.processed_at = now
        self._session.flush()

    def mark_failed(self, events: list[EventBuffer]) -> None:
        now = _utcnow()
        for row in events:
            row.status = EventStatus.failed
            row.processed_at = now
        self._session.flush()
