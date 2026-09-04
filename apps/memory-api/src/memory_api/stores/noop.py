from __future__ import annotations

import uuid
from datetime import datetime

from memory_api.stores.types import GraphEdge, KVFact


class NoOpKVStore:
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
    ) -> None:
        return None

    def get(self, org_id: uuid.UUID, fact_type: str, entity: str) -> KVFact | None:
        return None

    def search_keys(
        self, org_id: uuid.UUID, candidates: list[tuple[str, str]]
    ) -> list[KVFact]:
        return []

    def by_org(self, org_id: uuid.UUID, *, user_key: str | None = None) -> list[KVFact]:
        return []


class NoOpGraphStore:
    def upsert_node(
        self,
        org_id: uuid.UUID,
        entity_key: str,
        label: str,
        properties: dict | None = None,
    ) -> uuid.UUID:
        return uuid.uuid4()

    def add_edge(
        self,
        org_id: uuid.UUID,
        subject_key: str,
        relation: str,
        object_key: str,
        *,
        memory_id: uuid.UUID | None,
        confidence: float = 1.0,
    ) -> uuid.UUID:
        return uuid.uuid4()

    def neighbors(
        self,
        org_id: uuid.UUID,
        entity_key: str,
        *,
        hops: int = 1,
        valid_only: bool = True,
        as_of: datetime | None = None,
    ) -> list[GraphEdge]:
        return []

    def memories_for_subgraph(
        self, org_id: uuid.UUID, entity_keys: list[str], *, hops: int = 1
    ) -> list[uuid.UUID]:
        return []
