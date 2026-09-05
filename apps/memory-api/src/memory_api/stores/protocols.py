from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol

from memory_api.stores.types import GraphEdge, KVFact, ScoredMemory


class VectorStore(Protocol):
    def upsert(self, memory_id: uuid.UUID, embedding: list[float], metadata: dict) -> None: ...

    def search(
        self,
        org_id: uuid.UUID,
        query_embedding: list[float],
        *,
        session_id: str | None,
        limit: int,
    ) -> list[ScoredMemory]: ...


class KVStore(Protocol):
    def put(
        self,
        org_id: uuid.UUID,
        memory_id: uuid.UUID,
        fact_type: str,
        entity: str,
        *,
        value: str | None,
        importance: float,
        user_key: str | None = None,
    ) -> None: ...

    def get(self, org_id: uuid.UUID, fact_type: str, entity: str) -> KVFact | None: ...

    def search_keys(
        self, org_id: uuid.UUID, candidates: list[tuple[str, str]]
    ) -> list[KVFact]: ...

    def by_org(self, org_id: uuid.UUID, *, user_key: str | None = None) -> list[KVFact]: ...


class GraphStore(Protocol):
    def upsert_node(
        self,
        org_id: uuid.UUID,
        entity_key: str,
        label: str,
        properties: dict | None = None,
    ) -> uuid.UUID: ...

    def add_edge(
        self,
        org_id: uuid.UUID,
        subject_key: str,
        relation: str,
        object_key: str,
        *,
        memory_id: uuid.UUID | None,
        confidence: float = 1.0,
    ) -> uuid.UUID: ...

    def neighbors(
        self,
        org_id: uuid.UUID,
        entity_key: str,
        *,
        hops: int = 1,
        valid_only: bool = True,
        as_of: datetime | None = None,
    ) -> list[GraphEdge]: ...

    def memories_for_subgraph(
        self, org_id: uuid.UUID, entity_keys: list[str], *, hops: int = 1
    ) -> list[uuid.UUID]: ...

    def memory_hops(
        self,
        org_id: uuid.UUID,
        entity_keys: list[str],
        *,
        hops: int = 2,
        as_of: datetime | None = None,
    ) -> dict[uuid.UUID, int]: ...
