from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from memory_api.db.models import Memory


@dataclass(frozen=True)
class ScoredMemory:
    memory: Memory
    similarity: float


@dataclass(frozen=True)
class KVFact:
    org_id: uuid.UUID
    memory_id: uuid.UUID
    fact_type: str
    entity: str
    value: str | None
    importance: float
    user_key: str | None = None
    id: uuid.UUID | None = None


@dataclass(frozen=True)
class GraphEdge:
    org_id: uuid.UUID
    subject_key: str
    relation: str
    object_key: str
    memory_id: uuid.UUID | None = None
    valid: bool = True
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    confidence: float = 1.0
    properties: dict = field(default_factory=dict)
    id: uuid.UUID | None = None
