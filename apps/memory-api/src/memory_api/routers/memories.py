from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from memory_api.auth import get_principal, get_session_user
from memory_api.config import settings
from memory_api.db.deps import get_repository
from memory_api.db.models import Memory, MemoryType, User
from memory_api.db.repository import MemoryRepository
from memory_api.schemas.memory import (
    MemoryCreate,
    MemoryOut,
    MemorySearchResponse,
    MemoryUpdate,
    ScoreDetails,
)
from memory_api.services.api_keys import Principal
from memory_api.services.dedup import persist_candidate
from memory_api.services.embedding import Embedder, embed_text, get_embedder
from memory_api.services.extraction import Candidate
from memory_api.services.scoring import recency_weight, retrieval_score, truncate_to_token_budget

router = APIRouter()


def _to_out(
    memory: Memory,
    score: float | None = None,
    score_details: ScoreDetails | None = None,
) -> MemoryOut:
    payload = MemoryOut.model_validate(memory)
    payload.score = score
    payload.score_details = score_details
    return payload


@router.post("/memories", response_model=MemoryOut, status_code=status.HTTP_201_CREATED)
def create_memory(
    body: MemoryCreate,
    principal: Principal = Depends(get_principal),
    repo: MemoryRepository = Depends(get_repository),
    embedder: Embedder = Depends(get_embedder),
) -> MemoryOut:
    candidate = Candidate(
        content=body.content,
        memory_type=body.memory_type,
        importance=body.importance,
        source_metadata=body.source_metadata,
    )
    memory, _inserted = persist_candidate(
        repo=repo,
        embedder=embedder,
        org_id=principal.org_id,
        session_id=body.session_id,
        candidate=candidate,
        threshold=settings.dedup_threshold,
    )
    return _to_out(memory)


@router.get("/memories/search", response_model=MemorySearchResponse)
def search(
    q: str,
    session_id: str | None = None,
    limit: int = Query(default=10, ge=1, le=100),
    token_budget: int = Query(default=2048, ge=1, le=32_000),
    explain: bool = False,
    principal: Principal = Depends(get_principal),
    repo: MemoryRepository = Depends(get_repository),
    embedder: Embedder = Depends(get_embedder),
) -> MemorySearchResponse:
    query_embedding = embed_text(q, embedder=embedder)
    rows = repo.search(
        org_id=principal.org_id,
        query_embedding=query_embedding,
        session_id=session_id,
        limit=max(limit * 5, 20),
    )
    ranked: list[tuple[Memory, float, float, float, float]] = []
    for memory, similarity in rows:
        recency = recency_weight(
            memory.created_at, half_life_days=settings.recency_halflife_days
        )
        score = retrieval_score(
            similarity=similarity,
            importance=memory.importance,
            recency=recency,
            semantic_weight=settings.fusion_weight_relevance,
            importance_weight=settings.fusion_weight_importance,
            recency_weight_value=settings.fusion_weight_recency,
        )
        ranked.append((memory, score, similarity, recency, memory.importance))
    ranked.sort(key=lambda item: item[1], reverse=True)
    ranked = ranked[:limit]

    def _hit(
        memory: Memory, score: float, similarity: float, recency: float, importance: float
    ) -> MemoryOut:
        details = None
        if explain:
            details = ScoreDetails(
                relevance=similarity,
                importance=importance,
                recency=recency,
                sources=["vector"],
                vector_similarity=similarity,
                kv_match=None,
                graph_hops=None,
                weights={
                    "relevance": settings.fusion_weight_relevance,
                    "importance": settings.fusion_weight_importance,
                    "recency": settings.fusion_weight_recency,
                },
            )
        return _to_out(memory, score, details)

    memories = truncate_to_token_budget(
        [
            _hit(memory, score, similarity, recency, importance)
            for memory, score, similarity, recency, importance in ranked
        ],
        token_budget,
        text_of=lambda item: item.content,
    )
    return MemorySearchResponse(memories=memories)


@router.get("/memories", response_model=MemorySearchResponse)
def list_memories(
    session_id: str | None = None,
    memory_type: MemoryType | None = None,
    q: str | None = None,
    user: User = Depends(get_session_user),
    repo: MemoryRepository = Depends(get_repository),
) -> MemorySearchResponse:
    rows = repo.list(
        org_id=user.org_id,
        session_id=session_id,
        memory_type=memory_type,
        q=q,
    )
    return MemorySearchResponse(memories=[_to_out(memory) for memory in rows])


@router.patch("/memories/{memory_id}", response_model=MemoryOut)
def update_memory(
    memory_id: uuid.UUID,
    body: MemoryUpdate,
    principal: Principal = Depends(get_principal),
    repo: MemoryRepository = Depends(get_repository),
    embedder: Embedder = Depends(get_embedder),
) -> MemoryOut:
    memory = repo.get(org_id=principal.org_id, memory_id=memory_id)
    if memory is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")

    if body.content is not None:
        memory.content = body.content
        memory.embedding = embed_text(body.content, embedder=embedder)
    if body.importance is not None:
        memory.importance = body.importance
    if body.memory_type is not None:
        memory.memory_type = body.memory_type
    memory.updated_at = datetime.now(UTC)
    return _to_out(memory)


@router.delete("/memories/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def forget_memory(
    memory_id: uuid.UUID,
    principal: Principal = Depends(get_principal),
    repo: MemoryRepository = Depends(get_repository),
) -> None:
    deleted = repo.delete(org_id=principal.org_id, memory_id=memory_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
