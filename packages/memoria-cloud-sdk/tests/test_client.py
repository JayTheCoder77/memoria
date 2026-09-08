from __future__ import annotations

import uuid

import httpx
import pytest

from memoria_cloud import Memoria
from memoria_cloud.errors import MemoriaAuthError, MemoriaNotFoundError, MemoriaRateLimitError


def _memory_json(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": str(uuid.uuid4()),
        "org_id": str(uuid.uuid4()),
        "session_id": "s1",
        "memory_type": "semantic",
        "content": "remember this",
        "importance": 0.5,
        "access_count": 0,
        "source_metadata": {},
        "created_at": "2026-09-02T00:00:00+00:00",
        "updated_at": None,
        "last_accessed_at": None,
        "score": None,
    }
    payload.update(overrides)
    return payload


def _client(handler: object, **kwargs: object) -> Memoria:
    http = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://memory")
    return Memoria(http=http, api_key="mem_testkey", **kwargs)


def test_remember_posts_to_memory_api() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert request.headers["authorization"] == "Bearer mem_testkey"
        return httpx.Response(201, json=_memory_json(), request=request)

    memory = _client(handler).remember(content="remember this", session_id="s1")
    assert memory.content == "remember this"
    assert seen[0].method == "POST"
    assert seen[0].url.path == "/memories"


def test_recall_update_forget_emit_and_inspect_call_expected_routes() -> None:
    seen: list[httpx.Request] = []
    memory_id = str(uuid.uuid4())

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.method == "GET" and request.url.path == "/memories/search":
            return httpx.Response(200, json={"memories": []}, request=request)
        if request.method == "GET" and request.url.path == "/memories":
            return httpx.Response(200, json={"memories": []}, request=request)
        if request.method == "GET" and request.url.path == "/kv-facts":
            return httpx.Response(200, json={"facts": []}, request=request)
        if request.method == "GET" and request.url.path == "/graph-edges":
            return httpx.Response(200, json={"edges": []}, request=request)
        if request.method == "GET" and request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"}, request=request)
        if request.method == "PATCH":
            return httpx.Response(
                200,
                json=_memory_json(id=memory_id, content="updated"),
                request=request,
            )
        if request.method == "DELETE":
            return httpx.Response(204, request=request)
        if request.method == "POST" and request.url.path == "/events":
            return httpx.Response(
                202,
                json={"status": "queued", "id": str(uuid.uuid4())},
                request=request,
            )
        return httpx.Response(404, request=request)

    client = _client(handler)
    client.recall(q="org wide")
    assert "session_id" not in seen[0].url.params
    client.recall(q="remember this", session_id="s1")
    assert seen[1].url.params["session_id"] == "s1"
    client.recall(q="history", as_of="2026-03-01T00:00:00Z")
    assert seen[2].url.params["as_of"] == "2026-03-01T00:00:00Z"
    client.recall(q="why", explain=True)
    assert seen[3].url.params["explain"] == "true"
    client.update(memory_id, content="updated")
    client.forget(memory_id)
    emitted = client.emit(
        session_id="s1",
        event_type="message",
        payload={"content": "We prefer pytest"},
    )
    assert emitted.status == "queued"
    client.list_memories(session_id="s1", memory_type="semantic", q="prefer")
    client.kv_facts(limit=10, offset=5)
    client.graph_edges(valid_only=False)
    health = client.health()
    assert health["status"] == "ok"
    paths = [(item.method, item.url.path) for item in seen]
    assert paths == [
        ("GET", "/memories/search"),
        ("GET", "/memories/search"),
        ("GET", "/memories/search"),
        ("GET", "/memories/search"),
        ("PATCH", f"/memories/{memory_id}"),
        ("DELETE", f"/memories/{memory_id}"),
        ("POST", "/events"),
        ("GET", "/memories"),
        ("GET", "/kv-facts"),
        ("GET", "/graph-edges"),
        ("GET", "/health"),
    ]
    assert seen[8].url.params["limit"] == "10"
    assert seen[8].url.params["offset"] == "5"
    assert seen[9].url.params["valid_only"] == "false"


def test_default_base_url_and_env_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MEMORY_API_KEY", "mem_from_env")
    monkeypatch.delenv("MEMORY_API_URL", raising=False)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer mem_from_env"
        return httpx.Response(200, json={"status": "ok"}, request=request)

    client = Memoria(http=httpx.Client(transport=httpx.MockTransport(handler), base_url="http://memory"))
    assert client.base_url == "https://memoria-api-jw5g.onrender.com"
    assert client.health()["status"] == "ok"


def test_status_errors_are_typed() -> None:
    def unauthorized(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "Invalid or missing API key"})

    def missing(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"detail": "Memory not found"}, request=request)

    def limited(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"detail": "Rate limit exceeded"}, request=request)

    with pytest.raises(MemoriaAuthError, match="Invalid or missing API key"):
        _client(unauthorized).recall(q="nope")
    with pytest.raises(MemoriaNotFoundError, match="Memory not found"):
        _client(missing).forget(str(uuid.uuid4()))
    with pytest.raises(MemoriaRateLimitError, match="Rate limit exceeded"):
        _client(limited).recall(q="too many")


def test_missing_api_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MEMORY_API_KEY", raising=False)
    client = Memoria(
        http=httpx.Client(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"status": "ok"})),
            base_url="http://memory",
        )
    )
    with pytest.raises(MemoriaAuthError, match="MEMORY_API_KEY"):
        client.recall(q="no key")
