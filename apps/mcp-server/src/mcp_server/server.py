from __future__ import annotations

import os
from typing import Any

import httpx
from mcp.server.mcpserver import MCPServer

from mcp_server.client import MemoryApiClient

mcp = MCPServer("memoria", version="0.1.0")
_http = httpx.Client(base_url=os.environ.get("MEMORY_API_URL", "http://127.0.0.1:8000"))
client = MemoryApiClient(http=_http)


@mcp.tool()
def remember(
    org_id: str,
    session_id: str,
    api_key: str,
    content: str,
    memory_type: str = "semantic",
    importance: float = 0.5,
) -> dict[str, Any]:
    """Store a memory for the given org/session."""
    del org_id
    return client.remember(
        api_key=api_key,
        session_id=session_id,
        memory_type=memory_type,
        content=content,
        importance=importance,
    )


@mcp.tool()
def recall(
    org_id: str,
    session_id: str,
    api_key: str,
    q: str,
    limit: int = 10,
) -> dict[str, Any]:
    """Search memories by semantic similarity."""
    del org_id
    return client.recall(api_key=api_key, session_id=session_id, q=q, limit=limit)


@mcp.tool()
def update(
    org_id: str,
    session_id: str,
    api_key: str,
    memory_id: str,
    content: str | None = None,
    importance: float | None = None,
    memory_type: str | None = None,
) -> dict[str, Any]:
    """Update an existing memory."""
    del org_id, session_id
    return client.update(
        api_key=api_key,
        memory_id=memory_id,
        content=content,
        importance=importance,
        memory_type=memory_type,
    )


@mcp.tool()
def forget(
    org_id: str,
    session_id: str,
    api_key: str,
    memory_id: str,
) -> dict[str, str]:
    """Delete a memory."""
    del org_id, session_id
    client.forget(api_key=api_key, memory_id=memory_id)
    return {"status": "forgotten", "memory_id": memory_id}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
