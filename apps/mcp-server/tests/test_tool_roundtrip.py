from __future__ import annotations

import asyncio
import uuid

import httpx
import pytest

import mcp_server.server as server
from mcp_server.client import MemoryApiClient
from mcp_server.server import mcp


def test_remember_and_recall_tools_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    created_id = str(uuid.uuid4())

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(
                201,
                json={
                    "id": created_id,
                    "org_id": str(uuid.uuid4()),
                    "session_id": "s1",
                    "memory_type": "semantic",
                    "content": "round trip",
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
        return httpx.Response(
            200,
            json={
                "memories": [
                    {
                        "id": created_id,
                        "org_id": str(uuid.uuid4()),
                        "session_id": "s1",
                        "memory_type": "semantic",
                        "content": "round trip",
                        "importance": 0.5,
                        "access_count": 1,
                        "source_metadata": {},
                        "created_at": "2026-09-02T00:00:00+00:00",
                        "updated_at": None,
                        "last_accessed_at": None,
                        "score": 0.9,
                    }
                ]
            },
            request=request,
        )

    http = httpx.Client(transport=httpx.MockTransport(handler), base_url="http://memory")
    original = server.client
    server.client = MemoryApiClient(http=http)
    monkeypatch.setenv("MEMORY_API_KEY", "mem_test")
    try:
        remembered = asyncio.run(
            mcp.call_tool(
                "remember",
                {
                    "session_id": "s1",
                    "content": "round trip",
                },
            )
        )
        recalled = asyncio.run(
            mcp.call_tool(
                "recall",
                {
                    "session_id": "s1",
                    "q": "round trip",
                },
            )
        )
    finally:
        server.client = original
    assert remembered.is_error is False
    assert recalled.is_error is False
