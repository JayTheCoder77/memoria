from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from memory_api.auth import get_org_scope
from memory_api.db.deps import get_kv_store, get_repository
from memory_api.db.repository import MemoryRepository
from memory_api.services.profile import build_profile
from memory_api.services.scope import normalize_scope_id
from memory_api.stores.protocols import KVStore

router = APIRouter()


class ProfileFactOut(BaseModel):
    fact_type: str
    entity: str
    value: str | None


class ProfileOut(BaseModel):
    static: list[ProfileFactOut]
    dynamic: list[str]
    text: str


def _require_user_id(user_id: str) -> str:
    parsed = normalize_scope_id(user_id)
    if parsed is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="user_id is required",
        )
    return parsed


@router.get("/profile", response_model=ProfileOut)
def get_profile(
    user_id: str = Query(...),
    token_budget: int = Query(default=800, ge=1, le=32_000),
    org_id: uuid.UUID = Depends(get_org_scope),
    kv: KVStore = Depends(get_kv_store),
    repo: MemoryRepository = Depends(get_repository),
) -> ProfileOut:
    scoped_user = _require_user_id(user_id)
    profile = build_profile(
        org_id=org_id,
        user_id=scoped_user,
        token_budget=token_budget,
        kv=kv,
        repo=repo,
    )
    return ProfileOut(
        static=[
            ProfileFactOut(
                fact_type=fact.fact_type,
                entity=fact.entity,
                value=fact.value,
            )
            for fact in profile.static
        ],
        dynamic=profile.dynamic,
        text=profile.text,
    )
