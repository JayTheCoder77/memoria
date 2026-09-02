from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx
from mcp.server.mcpserver import MCPServer

from mcp_server.client import MemoryApiClient


def _load_dotenv() -> None:
    path = Path(__file__).resolve().parents[2] / ".env"
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'").strip('"'))


_load_dotenv()

mcp = MCPServer("memoria", version="0.1.0")
_http = httpx.Client(base_url=os.environ.get("MEMORY_API_URL", "http://127.0.0.1:8000"))
client = MemoryApiClient(http=_http)


def _api_key() -> str:
    key = os.environ.get("MEMORY_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "MEMORY_API_KEY is not set on the MCP server. Put the mem_ key in "
            "the MCP config environment, not in the prompt or AGENTS.md."
        )
    return key


def _session(session_id: str | None) -> str:
    value = (session_id or os.environ.get("MEMORY_SESSION_ID") or "").strip()
    if not value:
        raise RuntimeError("session_id is required (tool argument or MEMORY_SESSION_ID).")
    return value


@mcp.tool()
def remember(
    content: str,
    session_id: str | None = None,
    memory_type: str = "semantic",
    importance: float = 0.5,
) -> dict[str, Any]:
    """Store a durable memory. memory_type is episodic, semantic, or procedural."""
    return client.remember(
        api_key=_api_key(),
        session_id=_session(session_id),
        memory_type=memory_type,
        content=content,
        importance=importance,
    )


@mcp.tool()
def recall(
    q: str,
    session_id: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Search memories by semantic similarity."""
    return client.recall(
        api_key=_api_key(),
        session_id=_session(session_id),
        q=q,
        limit=limit,
    )


@mcp.tool()
def update(
    memory_id: str,
    content: str | None = None,
    importance: float | None = None,
    memory_type: str | None = None,
) -> dict[str, Any]:
    """Update an existing memory."""
    return client.update(
        api_key=_api_key(),
        memory_id=memory_id,
        content=content,
        importance=importance,
        memory_type=memory_type,
    )


@mcp.tool()
def forget(memory_id: str) -> dict[str, str]:
    """Delete a memory."""
    client.forget(api_key=_api_key(), memory_id=memory_id)
    return {"status": "forgotten", "memory_id": memory_id}


@mcp.tool()
def emit(
    event_type: str,
    payload: dict[str, Any] | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Buffer a harness event for async extraction. Not every event becomes a memory."""
    return client.emit(
        api_key=_api_key(),
        session_id=_session(session_id),
        event_type=event_type,
        payload=payload or {},
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
