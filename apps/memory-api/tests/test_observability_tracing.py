from __future__ import annotations

import json
import uuid

import httpx
import pytest
import structlog
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from memory_api.db.events import InMemoryEventStore
from memory_api.db.repository import InMemoryMemoryRepository
from memory_api.observability.logging import configure_logging
from memory_api.services.embedding import HashEmbedder
from memory_api.services.hybrid_search import HybridRetriever
from memory_api.services.llm_json import LlmProvider, complete_json
from memory_api.stores.graph import InMemoryGraphStore
from memory_api.stores.kv import InMemoryKVStore
from memory_api.stores.vector import PostgresVectorStore
from memory_api.worker import tick

QUERY = "where does ava live"
_ALLOWED_ATTRIBUTES = frozenset({"org_id", "embedder", "model", "store"})


def _exporter() -> InMemorySpanExporter:
    exporter = InMemorySpanExporter()
    provider = trace.get_tracer_provider()
    if not isinstance(provider, TracerProvider):
        provider = TracerProvider()
        trace.set_tracer_provider(provider)
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return exporter


def _attribute_text(span) -> str:
    attributes = span.attributes or {}
    return " ".join(str(value) for value in attributes.values())


class _LoggingEmbedder:
    def embed(self, text: str) -> list[float]:
        structlog.get_logger().info("during_embed")
        return HashEmbedder().embed(text)


def test_hybrid_search_opens_embed_and_vector_spans(capsys) -> None:
    configure_logging()
    exporter = _exporter()
    org_id = uuid.uuid4()
    repo = InMemoryMemoryRepository()
    retriever = HybridRetriever(
        repo=repo,
        vector=PostgresVectorStore(repo),
        kv=InMemoryKVStore(),
        graph=InMemoryGraphStore(),
        embedder=_LoggingEmbedder(),
    )
    capsys.readouterr()
    retriever.search(org_id=org_id, q=QUERY, session_id="s1")

    spans = exporter.get_finished_spans()
    names = {span.name for span in spans}
    assert "embed" in names
    assert "vector_search" in names
    assert "kv_search" in names
    assert "graph_search" in names
    by_name = {span.name: span for span in spans}
    assert by_name["vector_search"].attributes["store"] == "vector"
    assert by_name["vector_search"].attributes["org_id"] == str(org_id)
    assert by_name["kv_search"].attributes["store"] == "kv"
    assert by_name["graph_search"].attributes["store"] == "graph"
    assert isinstance(by_name["embed"].attributes["embedder"], str)
    for span in spans:
        attributes = span.attributes or {}
        assert set(attributes) <= _ALLOWED_ATTRIBUTES
        assert all(isinstance(value, str) for value in attributes.values())
        assert QUERY not in _attribute_text(span)

    embed = next(span for span in spans if span.name == "embed")
    during_embed = []
    for line in capsys.readouterr().out.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        payload = json.loads(line)
        if payload.get("event") == "during_embed":
            during_embed.append(payload)
    assert len(during_embed) == 1
    assert during_embed[0]["trace_id"] == format(embed.context.trace_id, "032x")
    assert set(during_embed[0]) == {
        "event",
        "org_id",
        "trace_id",
        "level",
        "timestamp",
    }


def test_complete_json_opens_llm_span_without_prompt() -> None:
    exporter = _exporter()
    prompt = "secret prompt where does ava live"

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"ok": true}'}}]},
        )

    payload = complete_json(
        [{"role": "user", "content": prompt}],
        providers=[
            LlmProvider(
                api_key="sk-test",
                base_url="https://example.invalid/v1",
                model="openai/gpt-4o-mini",
            )
        ],
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert payload == {"ok": True}
    spans = [span for span in exporter.get_finished_spans() if span.name == "llm_complete"]
    assert spans
    for span in spans:
        attributes = span.attributes or {}
        assert set(attributes) <= _ALLOWED_ATTRIBUTES
        assert all(isinstance(value, str) for value in attributes.values())
        assert attributes.get("model") == "openai/gpt-4o-mini"
        assert prompt not in _attribute_text(span)
        assert "sk-test" not in _attribute_text(span)


def test_tick_opens_worker_tick_span_without_memory_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exporter = _exporter()
    sentence = "We prefer the secret notebook over paper."
    events = InMemoryEventStore()
    org_id = uuid.uuid4()
    events.enqueue(
        org_id=org_id,
        session_id="s1",
        event_type="message",
        payload={"content": sentence},
    )
    events.enqueue(
        org_id=org_id,
        session_id="s1",
        event_type="session_end",
        payload={},
    )

    class _Session:
        def get(self, *_args: object, **_kwargs: object) -> None:
            return None

        def commit(self) -> None:
            return None

        def rollback(self) -> None:
            return None

        def close(self) -> None:
            return None

    monkeypatch.setattr("memory_api.worker.SessionLocal", lambda: _Session())
    monkeypatch.setattr("memory_api.worker.PostgresEventStore", lambda _session: events)
    monkeypatch.setattr(
        "memory_api.worker.PostgresMemoryRepository",
        lambda _session: InMemoryMemoryRepository(),
    )
    monkeypatch.setattr(
        "memory_api.worker.PostgresKVStore",
        lambda _session: InMemoryKVStore(),
    )
    monkeypatch.setattr(
        "memory_api.worker.PostgresGraphStore",
        lambda _session: InMemoryGraphStore(),
    )

    created = tick(embedder=HashEmbedder())
    assert created == 1
    spans = exporter.get_finished_spans()
    ticks = [span for span in spans if span.name == "worker_tick"]
    assert ticks
    for span in spans:
        attributes = span.attributes or {}
        assert set(attributes) <= _ALLOWED_ATTRIBUTES
        assert all(isinstance(value, str) for value in attributes.values())
        assert sentence not in _attribute_text(span)
