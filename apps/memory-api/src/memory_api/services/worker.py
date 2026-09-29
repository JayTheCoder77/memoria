from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from memory_api.db.events import EventStore
from memory_api.db.models import EventBuffer
from memory_api.db.repository import MemoryRepository
from memory_api.services.dedup import persist_candidate
from memory_api.services.embedding import Embedder
from memory_api.services.extraction import Extractor
from memory_api.services.graph_fanout import persist_graph_facts
from memory_api.services.kv_fanout import persist_kv_facts
from memory_api.services.webhooks import (
    PendingWebhook,
    collect_memory_written,
    post_webhooks,
    webhook_store_for,
)
from memory_api.stores.noop import NoOpGraphStore, NoOpKVStore
from memory_api.stores.protocols import GraphStore, KVStore


def _scope_value(payload: dict, key: str) -> str | None:
    raw = payload.get(key)
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    return text or None


def _batch_key(row: EventBuffer) -> tuple[object, str, str | None, str | None]:
    return (
        row.org_id,
        row.session_id,
        _scope_value(row.payload, "user_id"),
        _scope_value(row.payload, "agent_id"),
    )


def run_once(
    *,
    events: EventStore,
    repo: MemoryRepository,
    embedder: Embedder,
    extractor: Extractor,
    batch_size: int,
    threshold: float = 0.92,
    extractor_for_org: Callable[[UUID], Extractor] | None = None,
    kv: KVStore | None = None,
    graph: GraphStore | None = None,
    group_window_seconds: int = 120,
    deliveries: list[PendingWebhook] | None = None,
) -> int:
    kv = kv or NoOpKVStore()
    graph = graph or NoOpGraphStore()
    pending = deliveries if deliveries is not None else []
    claimed = events.claim_ready(batch_size, group_window_seconds=group_window_seconds)
    if not claimed:
        return 0
    try:
        created = 0
        grouped: dict[tuple[object, str], list[EventBuffer]] = {}
        for row in claimed:
            grouped.setdefault(_batch_key(row), []).append(row)
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
                kv=kv,
                graph=graph,
                deliveries=pending,
            )
    except Exception:
        events.mark_failed(claimed)
        raise
    events.mark_processed(claimed)
    if deliveries is None and getattr(repo, "_session", None) is None:
        post_webhooks(pending)
    return created


def _process(
    claimed: list[EventBuffer],
    *,
    repo: MemoryRepository,
    embedder: Embedder,
    extractor: Extractor,
    threshold: float,
    kv: KVStore,
    graph: GraphStore,
    deliveries: list[PendingWebhook],
) -> int:
    payload = [
        {"event_type": row.event_type, "payload": row.payload, "id": str(row.id)}
        for row in claimed
    ]
    created = 0
    session_id = claimed[0].session_id
    org_id = claimed[0].org_id
    user_id = _scope_value(claimed[0].payload, "user_id")
    agent_id = _scope_value(claimed[0].payload, "agent_id")
    for candidate in extractor.extract(payload):
        memory, inserted = persist_candidate(
            repo=repo,
            embedder=embedder,
            org_id=org_id,
            session_id=session_id,
            candidate=candidate,
            threshold=threshold,
            user_id=user_id,
            agent_id=agent_id,
        )
        persist_kv_facts(
            kv=kv,
            memory=memory,
            candidate=candidate,
            session=getattr(repo, "_session", None),
        )
        persist_graph_facts(
            graph=graph,
            memory=memory,
            candidate=candidate,
            session=getattr(repo, "_session", None),
        )
        if inserted:
            deliveries.extend(
                collect_memory_written(
                    webhook_store_for(repo),
                    memory_id=memory.id,
                    org_id=memory.org_id,
                    user_id=memory.user_id,
                )
            )
            created += 1
    return created
