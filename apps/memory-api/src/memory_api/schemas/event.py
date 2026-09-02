from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class EventCreate(BaseModel):
    session_id: str
    event_type: Literal["message", "tool_call", "diff", "session_end"]
    payload: dict[str, Any] = Field(default_factory=dict)


class EventIngestResponse(BaseModel):
    status: Literal["queued", "skipped"]
    id: str | None = None
