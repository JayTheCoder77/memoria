from __future__ import annotations

import json
import uuid

import httpx
import pytest

import mcp_server.server as server
from mcp_server.client import MemoryApiClient
from mcp_server.server import emit, remember, reset_auto_session


def _events_and_memories(request: httpx.Request) -> httpx.Response:
    if request.method == "POST" and request.url.path == "/events":
        return httpx.Response(
            202,
            json={"status": "queued", "id": str(uuid.uuid4())},
            request=request,
        )
    if request.method == "POST" and request.url.path == "/memories":
        body = json.loads(request.content)
        return httpx.Response(
            201,
            json={
                "id": str(uuid.uuid4()),
                "org_id": str(uuid.uuid4()),
                "session_id": body["session_id"],
                "memory_type": "semantic",
                "content": body["content"],
                "importance": 0.5,
                "access_count": 0,
                "source_metadata": {},
                "created_at": "2026-09-02T00:00:00+00:00",
                "updated_at": None,
                "last_accessed_at": None,
                "score": None,
            },
            request=request,
        )
    if request.method == "GET" and request.url.path == "/memories/search":
        return httpx.Response(200, json={"memories": []}, request=request)
    return httpx.Response(404, request=request)


@pytest.fixture
def patched_client(monkeypatch: pytest.MonkeyPatch) -> list[httpx.Request]:
    monkeypatch.delenv("MEMORY_SESSION_ID", raising=False)
    monkeypatch.setenv("MEMORY_API_KEY", "mem_test")
    reset_auto_session()
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return _events_and_memories(request)

    http = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://memory")
    original = server.client
    server.client = MemoryApiClient(http=http)
    yield seen
    server.client = original
    reset_auto_session()


def test_omitted_session_id_is_stable_for_writes(patched_client: list[httpx.Request]) -> None:
    remember(content="We prefer pytest")
    emit(event_type="message", payload={"content": "We prefer pytest"})
    bodies = [json.loads(item.content) for item in patched_client]
    assert bodies[0]["session_id"] == bodies[1]["session_id"]
    uuid.UUID(bodies[0]["session_id"])


def test_session_end_starts_a_new_auto_session(patched_client: list[httpx.Request]) -> None:
    emit(event_type="message", payload={"content": "We prefer pytest"})
    first = json.loads(patched_client[0].content)["session_id"]
    emit(event_type="session_end")
    emit(event_type="message", payload={"content": "We prefer bun"})
    third = json.loads(patched_client[2].content)["session_id"]
    assert third != first


def test_explicit_session_id_is_not_replaced(patched_client: list[httpx.Request]) -> None:
    remember(content="pin me", session_id="chat-99")
    assert json.loads(patched_client[0].content)["session_id"] == "chat-99"


def test_recall_without_session_id_searches_the_org(
    patched_client: list[httpx.Request],
) -> None:
    from mcp_server.server import recall

    recall(q="pytest")
    params = patched_client[0].url.params
    assert "session_id" not in params
    assert params["q"] == "pytest"
