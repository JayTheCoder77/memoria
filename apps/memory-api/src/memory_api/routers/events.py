from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from memory_api.auth import get_principal
from memory_api.db.deps import get_event_store
from memory_api.db.events import EventStore
from memory_api.schemas.event import EventCreate
from memory_api.services.api_keys import Principal
from memory_api.services.ingest import should_enqueue

router = APIRouter()


@router.post("/events")
def ingest_event(
    body: EventCreate,
    principal: Principal = Depends(get_principal),
    store: EventStore = Depends(get_event_store),
) -> JSONResponse:
    if not should_enqueue(body.event_type, body.payload):
        return JSONResponse({"status": "skipped"}, status_code=200)
    row = store.enqueue(
        org_id=principal.org_id,
        session_id=body.session_id,
        event_type=body.event_type,
        payload=body.payload,
    )
    return JSONResponse({"status": "queued", "id": str(row.id)}, status_code=202)
