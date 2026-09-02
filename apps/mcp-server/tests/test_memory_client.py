from __future__ import annotations

import uuid

import httpx

from mcp_server.client import MemoryApiClient


def _handler(request: httpx.Request) -> httpx.Response:
    if request.method == "POST" and request.url.path == "/memories":
        assert request.headers["authorization"] == "Bearer mem_testkey"
        return httpx.Response(
            201,
            json={
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
            },
            request=request,
        )
    if request.method == "GET" and request.url.path == "/memories/search":
        return httpx.Response(200, json={"memories": []}, request=request)
    if request.method == "PATCH":
        return httpx.Response(
            200,
            json={
                "id": request.url.path.split("/")[-1],
                "org_id": str(uuid.uuid4()),
                "session_id": "s1",
                "memory_type": "semantic",
                "content": "updated",
                "importance": 0.4,
                "access_count": 0,
                "source_metadata": {},
                "created_at": "2026-09-02T00:00:00+00:00",
                "updated_at": "2026-09-02T00:00:01+00:00",
                "last_accessed_at": None,
                "score": None,
            },
            request=request,
        )
    if request.method == "DELETE":
        return httpx.Response(204, request=request)
    return httpx.Response(404, request=request)


def test_remember_posts_to_memory_api() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return _handler(request)

    http = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://memory")
    client = MemoryApiClient(http=http)
    result = client.remember(
        api_key="mem_testkey",
        session_id="s1",
        memory_type="semantic",
        content="remember this",
    )
    assert result["content"] == "remember this"
    assert seen[0].method == "POST"
    assert seen[0].url.path == "/memories"


def test_recall_update_and_forget_call_expected_routes() -> None:
    seen: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        return _handler(request)

    http = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://memory")
    client = MemoryApiClient(http=http)
    memory_id = str(uuid.uuid4())
    client.recall(api_key="mem_testkey", session_id="s1", q="remember this")
    client.update(api_key="mem_testkey", memory_id=memory_id, content="updated")
    client.forget(api_key="mem_testkey", memory_id=memory_id)
    assert seen == [
        ("GET", "/memories/search"),
        ("PATCH", f"/memories/{memory_id}"),
        ("DELETE", f"/memories/{memory_id}"),
    ]
