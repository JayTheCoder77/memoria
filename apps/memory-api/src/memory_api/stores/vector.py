from __future__ import annotations

import uuid

from memory_api.db.repository import MemoryRepository
from memory_api.stores.types import ScoredMemory


class PostgresVectorStore:
    def __init__(self, repo: MemoryRepository) -> None:
        self._repo = repo

    def upsert(
        self, memory_id: uuid.UUID, embedding: list[float], metadata: dict
    ) -> None:
        return None

    def search(
        self,
        org_id: uuid.UUID,
        query_embedding: list[float],
        *,
        session_id: str | None,
        limit: int,
        embedding_model: str,
        user_id: str | None = None,
        agent_id: str | None = None,
    ) -> list[ScoredMemory]:
        rows = self._repo.search(
            org_id=org_id,
            query_embedding=query_embedding,
            session_id=session_id,
            limit=limit,
            embedding_model=embedding_model,
            user_id=user_id,
            agent_id=agent_id,
        )
        return [
            ScoredMemory(memory=memory, similarity=similarity)
            for memory, similarity in rows
        ]
