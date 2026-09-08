from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ScoreDetails(BaseModel):
    relevance: float
    importance: float
    recency: float
    sources: list[str]
    vector_similarity: float
    kv_match: float | None = None
    graph_hops: int | None = None
    weights: dict[str, float]


class Memory(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    session_id: str
    memory_type: str
    content: str
    importance: float
    access_count: int
    source_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime | None = None
    last_accessed_at: datetime | None = None
    score: float | None = None
    score_details: ScoreDetails | None = None


class MemorySearchResult(BaseModel):
    memories: list[Memory]
    timings_ms: dict[str, float] | None = None


class KvFact(BaseModel):
    fact_type: str
    entity: str
    value: str | None = None
    memory_id: uuid.UUID
    importance: float


class GraphEdge(BaseModel):
    subject: str
    relation: str
    object: str
    valid: bool
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    confidence: float
    memory_id: uuid.UUID | None = None


class EmitResult(BaseModel):
    status: Literal["queued", "skipped"]
    id: str | None = None
