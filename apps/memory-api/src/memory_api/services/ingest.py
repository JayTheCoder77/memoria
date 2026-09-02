from __future__ import annotations

from typing import Any

NOISY_TOOLS = {
    "read_file",
    "grep",
    "glob",
    "list_dir",
    "ls",
    "search_files",
    "read",
}

ALLOWED_EVENT_TYPES = {"message", "tool_call", "diff", "session_end"}


def should_enqueue(event_type: str, payload: dict[str, Any] | None) -> bool:
    body = payload or {}
    if event_type == "session_end":
        return True
    if event_type == "tool_call":
        tool = str(body.get("tool") or body.get("name") or "")
        if tool in NOISY_TOOLS and not body.get("important"):
            return False
    return event_type in ALLOWED_EVENT_TYPES
