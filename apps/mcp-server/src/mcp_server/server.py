from __future__ import annotations

import os
import uuid
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


_auto_session: str | None = None


def reset_auto_session() -> None:
    global _auto_session
    _auto_session = None


def _pinned_session() -> str:
    return os.environ.get("MEMORY_SESSION_ID", "").strip()


def _write_session(session_id: str | None) -> str:
    explicit = (session_id or "").strip()
    if explicit:
        return explicit
    pinned = _pinned_session()
    if pinned:
        return pinned
    global _auto_session
    if _auto_session is None:
        _auto_session = str(uuid.uuid4())
    return _auto_session


def _recall_session(session_id: str | None) -> str | None:
    explicit = (session_id or "").strip()
    if explicit:
        return explicit
    return _pinned_session() or None


def _rotate_auto_session(*, used_explicit: bool) -> None:
    if used_explicit or _pinned_session():
        return
    global _auto_session
    _auto_session = str(uuid.uuid4())


@mcp.tool()
def remember(
    content: str,
    session_id: str | None = None,
    memory_type: str = "semantic",
    importance: float = 0.5,
) -> dict[str, Any]:
    """Store a durable memory. memory_type is episodic, semantic, or procedural.

    Omit session_id. The adapter assigns one for this harness process and
    rotates it after emit(session_end). Do not put a session id in MCP JSON.
    """
    return client.remember(
        api_key=_api_key(),
        session_id=_write_session(session_id),
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
    """Search memories by semantic similarity across the org.

    Omit session_id unless you need to filter one conversation.
    """
    return client.recall(
        api_key=_api_key(),
        session_id=_recall_session(session_id),
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
    """Buffer a harness event for async extraction. Not every event becomes a memory.

    event_type must be message, tool_call, diff, or session_end. payload is an
    object (use content for text). Omit session_id. session_end flushes the
    worker batch and starts a new auto session id.
    """
    used_explicit = bool((session_id or "").strip())
    sid = _write_session(session_id)
    result = client.emit(
        api_key=_api_key(),
        session_id=sid,
        event_type=event_type,
        payload=payload or {},
    )
    if event_type == "session_end":
        _rotate_auto_session(used_explicit=used_explicit)
    return result


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
