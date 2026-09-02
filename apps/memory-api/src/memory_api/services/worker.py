from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from memory_api.db.events import EventStore
from memory_api.db.models import EventBuffer
from memory_api.db.repository import MemoryRepository
from memory_api.services.dedup import persist_candidate
from memory_api.services.embedding import Embedder
from memory_api.services.extraction import Extractor


def run_once(
    *,
    events: EventStore,
    repo: MemoryRepository,
    embedder: Embedder,
    extractor: Extractor,
    batch_size: int,
    threshold: float = 0.92,
    extractor_for_org: Callable[[UUID], Extractor] | None = None,
) -> int:
    claimed = events.claim_ready(batch_size)
    if not claimed:
        return 0
    try:
        created = 0
        grouped: dict[tuple[object, str], list[EventBuffer]] = {}
        for row in claimed:
            grouped.setdefault((row.org_id, row.session_id), []).append(row)
        for batch in grouped.values():
            org_id = batch[0].org_id
            batch_extractor = (
                extractor_for_org(org_id) if extractor_for_org is not None else extractor
            )
            created += _process(
                batch,
                repo=repo,
                embedder=embedder,
                extractor=batch_extractor,
                threshold=threshold,
            )
    except Exception:
        events.mark_failed(claimed)
        raise
    events.mark_processed(claimed)
    return created


def _process(
    claimed: list[EventBuffer],
    *,
    repo: MemoryRepository,
    embedder: Embedder,
    extractor: Extractor,
    threshold: float,
) -> int:
    payload = [
        {"event_type": row.event_type, "payload": row.payload, "id": str(row.id)}
        for row in claimed
    ]
    created = 0
    session_id = claimed[0].session_id
    org_id = claimed[0].org_id
    for candidate in extractor.extract(payload):
        _memory, inserted = persist_candidate(
            repo=repo,
            embedder=embedder,
            org_id=org_id,
            session_id=session_id,
            candidate=candidate,
            threshold=threshold,
        )
        if inserted:
            created += 1
    return created
