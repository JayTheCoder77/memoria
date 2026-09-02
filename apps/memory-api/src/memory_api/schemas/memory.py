from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from memory_api.db.models import MemoryType


class MemoryCreate(BaseModel):
    org_id: uuid.UUID
    session_id: str
    memory_type: MemoryType
    content: str
    importance: float = 0.5
    source_metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryUpdate(BaseModel):
    content: str | None = None
    importance: float | None = None
    memory_type: MemoryType | None = None


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
