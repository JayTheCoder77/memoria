from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query

from memory_api.auth import get_org_scope
from memory_api.db.deps import get_graph_store, get_kv_store
from memory_api.schemas.memory import (
    GraphEdgeListResponse,
    GraphEdgeOut,
    KvFactListResponse,
    KvFactOut,
)
from memory_api.stores.protocols import GraphStore, KVStore

router = APIRouter()


def _clamp_page(limit: int, offset: int) -> tuple[int, int]:
    return min(limit, 100), max(offset, 0)


@router.get("/kv-facts", response_model=KvFactListResponse)
def list_kv_facts(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    org_id: uuid.UUID = Depends(get_org_scope),
    kv: KVStore = Depends(get_kv_store),
) -> KvFactListResponse:
    limit, offset = _clamp_page(limit, offset)
    rows = sorted(kv.by_org(org_id), key=lambda row: (row.fact_type, row.entity))
    page = rows[offset : offset + limit]
    return KvFactListResponse(
        facts=[
            KvFactOut(
                fact_type=row.fact_type,
                entity=row.entity,
                value=row.value,
                memory_id=row.memory_id,
                importance=row.importance,
            )
            for row in page
        ]
    )


@router.get("/graph-edges", response_model=GraphEdgeListResponse)
def list_graph_edges(
    valid_only: bool = True,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    org_id: uuid.UUID = Depends(get_org_scope),
    graph: GraphStore = Depends(get_graph_store),
) -> GraphEdgeListResponse:
    limit, offset = _clamp_page(limit, offset)
    rows = sorted(
        graph.list_edges(org_id, valid_only=valid_only),
        key=lambda row: (row.subject_key, row.relation, row.object_key),
    )
    page = rows[offset : offset + limit]
    return GraphEdgeListResponse(
        edges=[
            GraphEdgeOut(
                subject=row.subject_key,
                relation=row.relation,
                object=row.object_key,
                valid=row.valid,
                valid_from=row.valid_from,
                valid_to=row.valid_to,
                confidence=row.confidence,
                memory_id=row.memory_id,
            )
            for row in page
        ]
    )
