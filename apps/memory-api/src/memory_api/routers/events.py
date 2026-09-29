from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from memory_api.auth import get_principal
from memory_api.db.deps import get_event_store
from memory_api.db.events import EventStore
from memory_api.schemas.event import EventCreate
from memory_api.services.api_keys import Principal
from memory_api.services.ingest import should_enqueue

router = APIRouter()


class PendingCount(BaseModel):
    pending: int
    failed: int


@router.post("/events")
def ingest_event(
    body: EventCreate,
    principal: Principal = Depends(get_principal),
    store: EventStore = Depends(get_event_store),
) -> JSONResponse:
    payload = dict(body.payload)
    if body.user_id is not None:
        payload["user_id"] = body.user_id
    if body.agent_id is not None:
        payload["agent_id"] = body.agent_id
    if not should_enqueue(body.event_type, payload):
        return JSONResponse({"status": "skipped"}, status_code=200)
    row = store.enqueue(
        org_id=principal.org_id,
        session_id=body.session_id,
        event_type=body.event_type,
        payload=payload,
    )
    return JSONResponse({"status": "queued", "id": str(row.id)}, status_code=202)


@router.get("/events/pending", response_model=PendingCount)
def pending_events(
    session_id: str = Query(min_length=1),
    principal: Principal = Depends(get_principal),
    store: EventStore = Depends(get_event_store),
) -> PendingCount:
    return PendingCount(
        pending=store.pending_count(org_id=principal.org_id, session_id=session_id),
        failed=store.failed_count(org_id=principal.org_id, session_id=session_id),
    )
