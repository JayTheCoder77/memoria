from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from memory_api.services.scope import normalize_scope_id


class EventCreate(BaseModel):
    session_id: str
    event_type: Literal["message", "tool_call", "diff", "session_end"]
    payload: dict[str, Any] = Field(default_factory=dict)
    user_id: str | None = None
    agent_id: str | None = None

    @field_validator("user_id", "agent_id", mode="before")
    @classmethod
    def _scope_id(cls, value: object) -> str | None:
        return normalize_scope_id(value)


class EventIngestResponse(BaseModel):
    status: Literal["queued", "skipped"]
    id: str | None = None
