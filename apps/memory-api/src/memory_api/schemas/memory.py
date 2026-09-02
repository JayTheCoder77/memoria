from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from memory_api.db.models import MemoryType

_MEMORY_TYPE_ALIASES = {
    "preference": MemoryType.semantic,
    "prefer": MemoryType.semantic,
    "fact": MemoryType.semantic,
    "knowledge": MemoryType.semantic,
    "note": MemoryType.semantic,
    "decision": MemoryType.semantic,
    "durable": MemoryType.semantic,
    "event": MemoryType.episodic,
    "episode": MemoryType.episodic,
    "session": MemoryType.episodic,
    "procedure": MemoryType.procedural,
    "process": MemoryType.procedural,
    "fix": MemoryType.procedural,
    "howto": MemoryType.procedural,
    "how_to": MemoryType.procedural,
}


def coerce_memory_type(value: object) -> MemoryType:
    if value is None or value == "":
        return MemoryType.semantic
    if isinstance(value, MemoryType):
        return value
    key = str(value).strip().lower().replace(" ", "_").replace("-", "_")
    if key in _MEMORY_TYPE_ALIASES:
        return _MEMORY_TYPE_ALIASES[key]
    return MemoryType(key)


class MemoryCreate(BaseModel):
    session_id: str
    memory_type: MemoryType = MemoryType.semantic
    content: str
    importance: float = 0.5
    source_metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("memory_type", mode="before")
    @classmethod
    def _memory_type(cls, value: object) -> MemoryType:
        return coerce_memory_type(value)

    @field_validator("importance", mode="before")
    @classmethod
    def _importance(cls, value: object) -> object:
        if value is None or value == "":
            return 0.5
        if isinstance(value, str):
            return float(value)
        return value


class MemoryUpdate(BaseModel):
    content: str | None = None
    importance: float | None = None
    memory_type: MemoryType | None = None

    @field_validator("memory_type", mode="before")
    @classmethod
    def _memory_type(cls, value: object) -> object:
        if value is None or value == "":
            return None
        return coerce_memory_type(value)


class MemoryOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    session_id: str
    memory_type: MemoryType
    content: str
    importance: float
    access_count: int
    source_metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime | None
    last_accessed_at: datetime | None
    score: float | None = None

    model_config = {"from_attributes": True}


class MemorySearchResponse(BaseModel):
    memories: list[MemoryOut]
