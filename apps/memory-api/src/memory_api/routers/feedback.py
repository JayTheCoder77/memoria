from __future__ import annotations

import uuid
from typing import Protocol

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from memory_api.auth import get_principal
from memory_api.db.deps import get_repository
from memory_api.db.models import MemoryFeedback
from memory_api.db.repository import MemoryRepository
from memory_api.schemas.memory import MemoryOut
from memory_api.services.api_keys import Principal

router = APIRouter()

_USEFUL_DELTA = 0.1
_NOT_USEFUL_DELTA = 0.2


class FeedbackIn(BaseModel):
    useful: bool


class FeedbackStore(Protocol):
    def record(
        self,
        *,
        org_id: uuid.UUID,
        memory_id: uuid.UUID,
        api_key_id: uuid.UUID,
        useful: bool,
    ) -> bool: ...


class InMemoryFeedbackStore:
    def __init__(self) -> None:
        self._votes: set[tuple[uuid.UUID, uuid.UUID]] = set()

    def record(
        self,
        *,
        org_id: uuid.UUID,
        memory_id: uuid.UUID,
        api_key_id: uuid.UUID,
        useful: bool,
    ) -> bool:
        del org_id, useful
        key = (memory_id, api_key_id)
        if key in self._votes:
            return False
        self._votes.add(key)
        return True


class PostgresFeedbackStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def record(
        self,
        *,
        org_id: uuid.UUID,
        memory_id: uuid.UUID,
        api_key_id: uuid.UUID,
        useful: bool,
    ) -> bool:
        existing = self._session.scalar(
            select(MemoryFeedback.id).where(
                MemoryFeedback.org_id == org_id,
                MemoryFeedback.memory_id == memory_id,
                MemoryFeedback.api_key_id == api_key_id,
            )
        )
        if existing is not None:
            return False
        self._session.add(
            MemoryFeedback(
                org_id=org_id,
                memory_id=memory_id,
                api_key_id=api_key_id,
                useful=useful,
            )
        )
        try:
            with self._session.begin_nested():
                self._session.flush()
        except IntegrityError as exc:
            if is_duplicate_vote(exc):
                return False
            raise
        return True


def is_duplicate_vote(exc: IntegrityError) -> bool:
    orig = exc.orig
    sqlstate = getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)
    if sqlstate == "23505":
        return True
    diag = getattr(orig, "diag", None)
    constraint = getattr(diag, "constraint_name", None) if diag is not None else None
    return constraint == "uq_memory_feedback_memory_api_key"


_in_memory_feedback = InMemoryFeedbackStore()


def feedback_store_for(repo: MemoryRepository) -> FeedbackStore:
    session = getattr(repo, "_session", None)
    if session is None:
        return _in_memory_feedback
    return PostgresFeedbackStore(session)


def adjusted_importance(importance: float, *, useful: bool) -> float:
    if useful:
        return min(1.0, importance + _USEFUL_DELTA)
    return max(0.0, importance - _NOT_USEFUL_DELTA)


@router.post("/memories/{memory_id}/feedback", response_model=MemoryOut)
def submit_feedback(
    memory_id: uuid.UUID,
    body: FeedbackIn,
    principal: Principal = Depends(get_principal),
    repo: MemoryRepository = Depends(get_repository),
) -> MemoryOut:
    if principal.api_key_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    memory = repo.get(org_id=principal.org_id, memory_id=memory_id)
    if memory is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found")
    recorded = feedback_store_for(repo).record(
        org_id=principal.org_id,
        memory_id=memory.id,
        api_key_id=principal.api_key_id,
        useful=body.useful,
    )
    if not recorded:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Feedback already recorded for this API key",
        )
    memory.importance = adjusted_importance(memory.importance, useful=body.useful)
    return MemoryOut.model_validate(memory)
