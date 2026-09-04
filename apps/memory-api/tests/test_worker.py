from __future__ import annotations

import uuid

from memory_api.db.events import InMemoryEventStore
from memory_api.db.models import EventStatus, MemoryType
from memory_api.db.repository import InMemoryMemoryRepository
from memory_api.services.embedding import HashEmbedder
from memory_api.services.extraction import HeuristicExtractor
from memory_api.services.worker import run_once
from memory_api.stores.graph import InMemoryGraphStore
from memory_api.stores.kv import InMemoryKVStore


def test_worker_extracts_on_session_end_and_skips_noise() -> None:
    events = InMemoryEventStore()
    repo = InMemoryMemoryRepository()
    org_id = uuid.uuid4()
    events.enqueue(
        org_id=org_id,
        session_id="s1",
        event_type="tool_call",
        payload={"tool": "ls", "content": "listed files"},
    )
    events.enqueue(
        org_id=org_id,
        session_id="s1",
        event_type="message",
        payload={"content": "We prefer pytest over unittest."},
    )
    events.enqueue(
        org_id=org_id,
        session_id="s1",
        event_type="session_end",
        payload={},
    )
    created = run_once(
        events=events,
        repo=repo,
        embedder=HashEmbedder(),
        extractor=HeuristicExtractor(),
        batch_size=10,
    )
    assert created == 1
    assert len(repo._rows) == 1
    assert repo._rows[0].memory_type == MemoryType.semantic
    assert all(row.status == EventStatus.processed for row in events._rows)


def test_worker_persists_kv_facts_for_extracted_candidates() -> None:
    events = InMemoryEventStore()
    repo = InMemoryMemoryRepository()
    kv = InMemoryKVStore()
    org_id = uuid.uuid4()
    events.enqueue(
        org_id=org_id,
        session_id="s1",
        event_type="message",
        payload={"content": "We prefer pytest over unittest."},
    )
    events.enqueue(
        org_id=org_id,
        session_id="s1",
        event_type="session_end",
        payload={},
    )
    created = run_once(
        events=events,
        repo=repo,
        embedder=HashEmbedder(),
        extractor=HeuristicExtractor(),
        batch_size=10,
        kv=kv,
    )
    assert created == 1
    assert kv.get(org_id, "preference", "pytest") is not None


def test_worker_persists_graph_facts_for_extracted_candidates() -> None:
    events = InMemoryEventStore()
    repo = InMemoryMemoryRepository()
    graph = InMemoryGraphStore()
    org_id = uuid.uuid4()
    events.enqueue(
        org_id=org_id,
        session_id="s1",
        event_type="message",
        payload={"content": "We decided Ava lives in Berlin."},
    )
    events.enqueue(
        org_id=org_id,
        session_id="s1",
        event_type="session_end",
        payload={},
    )
    created = run_once(
        events=events,
        repo=repo,
        embedder=HashEmbedder(),
        extractor=HeuristicExtractor(),
        batch_size=10,
        graph=graph,
    )
    assert created == 1
    edges = graph.neighbors(org_id, "user", hops=1)
    assert any(e.relation == "lives_in" and e.object_key == "berlin" for e in edges)


def test_worker_waits_until_batch_size_without_session_end() -> None:
    events = InMemoryEventStore()
    repo = InMemoryMemoryRepository()
    org_id = uuid.uuid4()
    events.enqueue(
        org_id=org_id,
        session_id="s1",
        event_type="message",
        payload={"content": "We prefer bun for JS."},
    )
    created = run_once(
        events=events,
        repo=repo,
        embedder=HashEmbedder(),
        extractor=HeuristicExtractor(),
        batch_size=10,
    )
    assert created == 0
    assert events._rows[0].status == EventStatus.pending
