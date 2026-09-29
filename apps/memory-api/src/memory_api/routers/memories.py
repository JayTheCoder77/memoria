from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError

from memory_api.auth import get_org_scope, get_principal
from memory_api.config import settings
from memory_api.db.deps import get_graph_store, get_kv_store, get_repository, get_vector_store
from memory_api.db.models import Memory, MemoryType, Org
from memory_api.db.repository import MemoryRepository
from memory_api.schemas.memory import (
    MemoryCreate,
    MemoryOut,
    MemorySearch,
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
from memory_api.services.hybrid_triples import enrich_hybrid_triples
from memory_api.services.kv_fanout import persist_kv_facts
from memory_api.services.org_llm import org_chat_providers
from memory_api.services.scoring import fused_relevance
from memory_api.services.webhooks import deliver_memory_written, webhook_store_for
from memory_api.stores.protocols import GraphStore, KVStore, VectorStore

router = APIRouter()


def _parse_metadata(raw: str | None) -> dict | None:
    if raw is None or raw == "":
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="metadata must be a JSON object",
        ) from exc
    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="metadata must be a JSON object",
        )
    return parsed


def _parse_scope(user_id: str | None, agent_id: str | None) -> tuple[str | None, str | None]:
    try:
        parsed = MemorySearch(q="scope", user_id=user_id, agent_id=agent_id)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.errors()
        ) from exc
    return parsed.user_id, parsed.agent_id


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
    if (
        (settings.enable_kv or settings.enable_graph)
        and not candidate.kv_triples
        and not candidate.graph_triples
    ):
        session = getattr(repo, "_session", None)
        org = session.get(Org, principal.org_id) if session is not None else None
        providers = org_chat_providers(org, timeout=10.0)
        kv_triples, graph_triples = enrich_hybrid_triples(
            body.content,
            providers=providers,
            org_id=principal.org_id,
        )
        if kv_triples or graph_triples:
            candidate = Candidate(
                content=body.content,
                memory_type=body.memory_type,
                importance=body.importance,
                source_metadata=body.source_metadata,
                kv_triples=kv_triples,
                graph_triples=graph_triples,
            )
    memory, _inserted = persist_candidate(
        repo=repo,
        embedder=embedder,
        org_id=principal.org_id,
        session_id=body.session_id,
        candidate=candidate,
        threshold=settings.dedup_threshold,
        user_id=body.user_id,
        agent_id=body.agent_id,
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
    if _inserted:
        deliver_memory_written(
            webhook_store_for(repo),
            memory_id=memory.id,
            org_id=memory.org_id,
            user_id=memory.user_id,
        )
    return _to_out(memory)


@router.get("/memories/search", response_model=MemorySearchResponse)
def search(
    q: str,
    session_id: str | None = None,
    limit: int = Query(default=10, ge=1, le=100),
    token_budget: int = Query(default=2048, ge=1, le=32_000),
    explain: bool = False,
    rerank: bool = False,
    as_of: datetime | None = None,
    user_id: str | None = None,
    agent_id: str | None = None,
    metadata: str | None = None,
    principal: Principal = Depends(get_principal),
    repo: MemoryRepository = Depends(get_repository),
    embedder: Embedder = Depends(get_embedder),
    vector: VectorStore = Depends(get_vector_store),
    kv: KVStore = Depends(get_kv_store),
    graph: GraphStore = Depends(get_graph_store),
) -> MemorySearchResponse:
    user_id, agent_id = _parse_scope(user_id, agent_id)
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
        user_id=user_id,
        agent_id=agent_id,
        rerank=rerank,
        metadata=_parse_metadata(metadata),
    )

    def _hit(item: RankedHit) -> MemoryOut:
        details = None
        if explain:
            graph_score = (
                1.0 if item.graph_hops == 1 else 0.5 if item.graph_hops == 2 else 0.0
            )
            relevance = fused_relevance(
                vector_similarity=item.similarity,
                lexical=item.lexical,
                kv_match=item.kv_match,
                graph_score=graph_score,
            )
            sources = []
            if item.vector_hit:
                sources.append("vector")
            if item.lexical > 0:
                sources.append("lexical")
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
                lexical=item.lexical,
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
    user_id: str | None = None,
    agent_id: str | None = None,
    metadata: str | None = None,
    org_id: uuid.UUID = Depends(get_org_scope),
    repo: MemoryRepository = Depends(get_repository),
) -> MemorySearchResponse:
    user_id, agent_id = _parse_scope(user_id, agent_id)
    rows = repo.list(
        org_id=org_id,
        session_id=session_id,
        memory_type=memory_type,
        q=q,
        user_id=user_id,
        agent_id=agent_id,
        metadata=_parse_metadata(metadata),
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
        memory.embedding_model = embedder.model_name
        memory.embedding_version += 1
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
