from __future__ import annotations

import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime

from memory_api.config import settings
from memory_api.db.models import Memory
from memory_api.db.repository import MemoryRepository, PostgresMemoryRepository
from memory_api.observability.tracing import start_span
from memory_api.services.embedding import Embedder, embed_text
from memory_api.services.graph_seeds import derive_graph_seeds
from memory_api.services.kv_candidates import derive_kv_candidates
from memory_api.services.rerank import RERANK_MODEL, rerank
from memory_api.services.scope import scope_matches
from memory_api.services.scoring import (
    fused_relevance,
    recency_weight,
    retrieval_score,
    truncate_to_token_budget,
)
from memory_api.stores.graph import PostgresGraphStore
from memory_api.stores.kv import PostgresKVStore
from memory_api.stores.protocols import GraphStore, KVStore, VectorStore
from memory_api.stores.types import KVFact, ScoredMemory
from memory_api.stores.vector import PostgresVectorStore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchTimings:
    embed_ms: float = 0.0
    vector_ms: float = 0.0
    kv_ms: float = 0.0
    graph_ms: float = 0.0
    total_ms: float = 0.0

    def as_dict(self) -> dict[str, float]:
        return {
            "embed": self.embed_ms,
            "vector": self.vector_ms,
            "kv": self.kv_ms,
            "graph": self.graph_ms,
            "total": self.total_ms,
        }


@dataclass(frozen=True)
class RankedHit:
    memory: Memory
    score: float
    similarity: float
    recency: float
    importance: float
    vector_hit: bool
    kv_match: float | None
    graph_hops: int | None
    lexical: float


@dataclass(frozen=True)
class HybridSearchResult:
    hits: list[RankedHit]
    timings: SearchTimings


def _elapsed_ms(started: float) -> float:
    return (time.perf_counter() - started) * 1000.0


def _store_span_attributes(org_id: uuid.UUID, store: str) -> dict[str, str]:
    return {"org_id": str(org_id), "store": store}


@dataclass
class _Candidate:
    memory: Memory
    similarity: float
    vector_hit: bool
    kv_match: float | None
    graph_hops: int | None
    lexical: float


def _memory_in_scope(
    memory: Memory,
    *,
    session_id: str | None,
    user_id: str | None,
    agent_id: str | None,
) -> bool:
    if session_id is not None and memory.session_id != session_id:
        return False
    return scope_matches(memory.user_id, memory.agent_id, user_id=user_id, agent_id=agent_id)


def _rerank_hits(query: str, hits: list[RankedHit], *, limit: int) -> list[RankedHit]:
    return rerank(query, hits, limit=limit)


def _graph_score(graph_hops: int | None) -> float:
    if graph_hops == 1:
        return 1.0
    if graph_hops == 2:
        return 0.5
    return 0.0


class HybridRetriever:
    def __init__(
        self,
        *,
        repo: MemoryRepository,
        vector: VectorStore,
        kv: KVStore,
        graph: GraphStore,
        embedder: Embedder,
    ) -> None:
        self._repo = repo
        self._vector = vector
        self._kv = kv
        self._graph = graph
        self._embedder = embedder

    def _vector_is_postgres(self) -> bool:
        inner = getattr(self._vector, "_repo", None)
        return isinstance(self._vector, PostgresVectorStore) and isinstance(
            inner, PostgresMemoryRepository
        )

    def search(
        self,
        *,
        org_id: uuid.UUID,
        q: str,
        session_id: str | None = None,
        limit: int = 10,
        token_budget: int = 2048,
        as_of: datetime | None = None,
        user_id: str | None = None,
        agent_id: str | None = None,
        rerank: bool = False,
    ) -> HybridSearchResult:
        total_started = time.perf_counter()
        embed_started = time.perf_counter()
        query_embedding = embed_text(q, embedder=self._embedder)
        embed_ms = _elapsed_ms(embed_started)
        vector_limit = max(limit * 5, 20)
        with ThreadPoolExecutor(max_workers=4) as pool:
            vector_future = pool.submit(
                self._vector_search,
                org_id,
                query_embedding,
                session_id,
                vector_limit,
                user_id,
                agent_id,
            )
            kv_future = pool.submit(self._kv_search, org_id, q, user_id, agent_id)
            graph_future = pool.submit(
                self._graph_search, org_id, q, as_of, user_id, agent_id
            )
            lexical_future = pool.submit(
                self._lexical_search,
                org_id,
                q,
                session_id,
                vector_limit,
                user_id,
                agent_id,
            )
            scored, vector_ms = vector_future.result()
            facts, kv_ms = kv_future.result()
            hops_map, graph_ms = graph_future.result()
            lexical_hits, _lexical_ms = lexical_future.result()

        union: dict[uuid.UUID, _Candidate] = {
            item.memory.id: _Candidate(
                memory=item.memory,
                similarity=item.similarity,
                vector_hit=True,
                kv_match=None,
                graph_hops=None,
                lexical=0.0,
            )
            for item in scored
        }

        for memory_id, lexical_score in lexical_hits:
            existing = union.get(memory_id)
            if existing is not None:
                existing.lexical = lexical_score
                continue
            memory = self._repo.get(org_id=org_id, memory_id=memory_id)
            if memory is None or not _memory_in_scope(
                memory, session_id=session_id, user_id=user_id, agent_id=agent_id
            ):
                continue
            union[memory_id] = _Candidate(
                memory=memory,
                similarity=0.0,
                vector_hit=False,
                kv_match=None,
                graph_hops=None,
                lexical=lexical_score,
            )

        for fact in facts:
            existing = union.get(fact.memory_id)
            if existing is not None:
                existing.kv_match = 1.0
                continue
            memory = self._repo.get(org_id=org_id, memory_id=fact.memory_id)
            if memory is None or not _memory_in_scope(
                memory, session_id=session_id, user_id=user_id, agent_id=agent_id
            ):
                continue
            union[fact.memory_id] = _Candidate(
                memory=memory,
                similarity=0.0,
                vector_hit=False,
                kv_match=1.0,
                graph_hops=None,
                lexical=0.0,
            )

        for memory_id, hop_count in hops_map.items():
            existing = union.get(memory_id)
            if existing is not None:
                existing.graph_hops = hop_count
                continue
            memory = self._repo.get(org_id=org_id, memory_id=memory_id)
            if memory is None or not _memory_in_scope(
                memory, session_id=session_id, user_id=user_id, agent_id=agent_id
            ):
                continue
            union[memory_id] = _Candidate(
                memory=memory,
                similarity=0.0,
                vector_hit=False,
                kv_match=None,
                graph_hops=hop_count,
                lexical=0.0,
            )

        ranked: list[RankedHit] = []
        for candidate in union.values():
            recency = recency_weight(
                candidate.memory.created_at,
                half_life_days=settings.recency_halflife_days,
            )
            relevance = fused_relevance(
                vector_similarity=candidate.similarity,
                lexical=candidate.lexical,
                kv_match=candidate.kv_match,
                graph_score=_graph_score(candidate.graph_hops),
            )
            score = retrieval_score(
                similarity=relevance,
                importance=candidate.memory.importance,
                recency=recency,
                semantic_weight=settings.fusion_weight_relevance,
                importance_weight=settings.fusion_weight_importance,
                recency_weight_value=settings.fusion_weight_recency,
            )
            ranked.append(
                RankedHit(
                    memory=candidate.memory,
                    score=score,
                    similarity=candidate.similarity,
                    recency=recency,
                    importance=candidate.memory.importance,
                    vector_hit=candidate.vector_hit,
                    kv_match=candidate.kv_match,
                    graph_hops=candidate.graph_hops,
                    lexical=candidate.lexical,
                )
            )
        ranked.sort(key=lambda item: item.score, reverse=True)
        if rerank:
            with start_span("rerank", org_id=str(org_id), model=RERANK_MODEL):
                ranked = _rerank_hits(q, ranked, limit=limit)
        else:
            ranked = ranked[:limit]
        hits = truncate_to_token_budget(
            ranked,
            token_budget,
            text_of=lambda item: item.memory.content,
        )
        timings = SearchTimings(
            embed_ms=embed_ms,
            vector_ms=vector_ms,
            kv_ms=kv_ms,
            graph_ms=graph_ms,
            total_ms=_elapsed_ms(total_started),
        )
        logger.info("hybrid_search_timings %s", timings.as_dict())
        return HybridSearchResult(hits=hits, timings=timings)

    def _lexical_search(
        self,
        org_id: uuid.UUID,
        q: str,
        session_id: str | None,
        limit: int,
        user_id: str | None,
        agent_id: str | None,
    ) -> tuple[list[tuple[uuid.UUID, float]], float]:
        started = time.perf_counter()
        with start_span("lexical_search", org_id=str(org_id), store="lexical"):
            if not self._vector_is_postgres():
                return [], _elapsed_ms(started)
            session = None
            try:
                from memory_api.db.session import SessionLocal
                from memory_api.services.lexical import lexical_search

                session = SessionLocal()
                rows = lexical_search(
                    session,
                    org_id=org_id,
                    q=q,
                    session_id=session_id,
                    limit=limit,
                    embedding_model=self._embedder.model_name,
                    user_id=user_id,
                    agent_id=agent_id,
                )
                return rows, _elapsed_ms(started)
            except Exception as exc:
                logger.error(
                    "Lexical search failed; using other results only (%s)",
                    type(exc).__name__,
                )
                return [], _elapsed_ms(started)
            finally:
                if session is not None:
                    session.close()

    def _vector_search(
        self,
        org_id: uuid.UUID,
        query_embedding: list[float],
        session_id: str | None,
        limit: int,
        user_id: str | None,
        agent_id: str | None,
    ) -> tuple[list[ScoredMemory], float]:
        started = time.perf_counter()
        with start_span("vector_search", org_id=str(org_id), store="vector"):
            try:
                store = self._vector
                session = None
                if self._vector_is_postgres():
                    from memory_api.db.session import SessionLocal

                    session = SessionLocal()
                    store = PostgresVectorStore(PostgresMemoryRepository(session))
                try:
                    rows = store.search(
                        org_id,
                        query_embedding,
                        session_id=session_id,
                        limit=limit,
                        embedding_model=self._embedder.model_name,
                        user_id=user_id,
                        agent_id=agent_id,
                    )
                finally:
                    if session is not None:
                        session.close()
                return rows, _elapsed_ms(started)
            except Exception:
                logger.exception("Vector search failed; using KV/graph results only")
                return [], _elapsed_ms(started)

    def _kv_search(
        self,
        org_id: uuid.UUID,
        q: str,
        user_id: str | None,
        agent_id: str | None,
    ) -> tuple[list[KVFact], float]:
        if not settings.enable_kv:
            return [], 0.0
        started = time.perf_counter()
        with start_span("kv_search", **_store_span_attributes(org_id, "kv")):
            try:
                candidates = derive_kv_candidates(q)
                store = self._kv
                session = None
                if isinstance(self._kv, PostgresKVStore):
                    from memory_api.db.session import SessionLocal

                    session = SessionLocal()
                    store = PostgresKVStore(session)
                try:
                    facts = store.search_keys(
                        org_id, candidates, user_id=user_id, agent_id=agent_id
                    )
                finally:
                    if session is not None:
                        session.close()
                return facts, _elapsed_ms(started)
            except Exception:
                logger.exception("KV search failed; using vector results only")
                return [], _elapsed_ms(started)

    def _graph_search(
        self,
        org_id: uuid.UUID,
        q: str,
        as_of: datetime | None,
        user_id: str | None,
        agent_id: str | None,
    ) -> tuple[dict[uuid.UUID, int], float]:
        if not settings.enable_graph:
            return {}, 0.0
        started = time.perf_counter()
        with start_span("graph_search", **_store_span_attributes(org_id, "graph")):
            try:
                seeds = derive_graph_seeds(q)
                store = self._graph
                session = None
                if isinstance(self._graph, PostgresGraphStore):
                    from memory_api.db.session import SessionLocal

                    session = SessionLocal()
                    store = PostgresGraphStore(session)
                try:
                    hops_map = store.memory_hops(
                        org_id,
                        seeds,
                        hops=2,
                        as_of=as_of,
                        user_id=user_id,
                        agent_id=agent_id,
                    )
                finally:
                    if session is not None:
                        session.close()
                return hops_map, _elapsed_ms(started)
            except Exception:
                logger.exception("Graph search failed; using vector/KV results only")
                return {}, _elapsed_ms(started)
