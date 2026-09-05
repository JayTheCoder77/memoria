from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from memory_api.auth import get_principal, get_session_user
from memory_api.config import settings
from memory_api.db.deps import get_graph_store, get_kv_store, get_repository, get_vector_store
from memory_api.db.models import Memory, MemoryType, Org, User
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
from memory_api.services.graph_fanout import persist_graph_facts
from memory_api.services.hybrid_search import HybridRetriever, RankedHit
from memory_api.services.kv_fanout import persist_kv_facts
from memory_api.services.secrets import decrypt_secret
from memory_api.stores.protocols import GraphStore, KVStore, VectorStore

logger = logging.getLogger(__name__)
router = APIRouter()


def _org_llm_key(
    repo: MemoryRepository, org_id: uuid.UUID
) -> tuple[str | None, str | None]:
    session = getattr(repo, "_session", None)
    if session is None:
        return None, None
    org = session.get(Org, org_id)
    if org is None or not org.openrouter_key_ciphertext:
        return None, None
    try:
        return decrypt_secret(org.openrouter_key_ciphertext), org.openrouter_model
    except Exception:
        logger.exception("Failed to decrypt org OpenRouter key; using rules fallback")
        return None, None


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
    kv: KVStore = Depends(get_kv_store),
    graph: GraphStore = Depends(get_graph_store),
) -> MemoryOut:
    candidate = Candidate(
        content=body.content,
        memory_type=body.memory_type,
        importance=body.importance,
        source_metadata=body.source_metadata,
        kv_triples=body.kv_triples,
        graph_triples=body.graph_triples,
    )
    memory, _inserted = persist_candidate(
        repo=repo,
        embedder=embedder,
        org_id=principal.org_id,
        session_id=body.session_id,
        candidate=candidate,
        threshold=settings.dedup_threshold,
    )
    persist_kv_facts(
        kv=kv,
        memory=memory,
        candidate=candidate,
        session=getattr(repo, "_session", None),
    )
    persist_graph_facts(
        graph=graph,
        memory=memory,
        candidate=candidate,
        session=getattr(repo, "_session", None),
    )
    return _to_out(memory)


@router.get("/memories/search", response_model=MemorySearchResponse)
def search(
    q: str,
    session_id: str | None = None,
    limit: int = Query(default=10, ge=1, le=100),
    token_budget: int = Query(default=2048, ge=1, le=32_000),
    explain: bool = False,
    as_of: datetime | None = None,
    principal: Principal = Depends(get_principal),
    repo: MemoryRepository = Depends(get_repository),
    embedder: Embedder = Depends(get_embedder),
    vector: VectorStore = Depends(get_vector_store),
    kv: KVStore = Depends(get_kv_store),
    graph: GraphStore = Depends(get_graph_store),
) -> MemorySearchResponse:
    api_key: str | None = None
    model: str | None = None
    if settings.enable_kv or settings.enable_graph:
        api_key, model = _org_llm_key(repo, principal.org_id)
    result = HybridRetriever(
        repo=repo,
        vector=vector,
        kv=kv,
        graph=graph,
        embedder=embedder,
    ).search(
        org_id=principal.org_id,
        q=q,
        session_id=session_id,
        limit=limit,
        token_budget=token_budget,
        as_of=as_of,
        api_key=api_key,
        model=model,
    )

    def _hit(item: RankedHit) -> MemoryOut:
        details = None
        if explain:
            graph_score = (
                1.0 if item.graph_hops == 1 else 0.5 if item.graph_hops == 2 else 0.0
            )
            relevance = max(item.similarity, item.kv_match or 0.0, graph_score)
            sources = []
            if item.vector_hit:
                sources.append("vector")
            if item.kv_match is not None:
                sources.append("kv")
            if item.graph_hops is not None:
                sources.append("graph")
            details = ScoreDetails(
                relevance=relevance,
                importance=item.importance,
                recency=item.recency,
                sources=sources,
                vector_similarity=item.similarity,
                kv_match=item.kv_match,
                graph_hops=item.graph_hops,
                weights={
                    "relevance": settings.fusion_weight_relevance,
                    "importance": settings.fusion_weight_importance,
                    "recency": settings.fusion_weight_recency,
                },
            )
        return _to_out(item.memory, item.score, details)

    return MemorySearchResponse(
        memories=[_hit(item) for item in result.hits],
        timings_ms=result.timings.as_dict() if explain else None,
    )


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
