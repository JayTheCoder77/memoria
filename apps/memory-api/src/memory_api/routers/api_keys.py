from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from memory_api.auth import get_session_user
from memory_api.db.deps import get_identity_repository
from memory_api.db.identity import IdentityRepository
from memory_api.db.models import User
from memory_api.schemas.auth import ApiKeyCreated, ApiKeyOut

router = APIRouter()


@router.post("/api-keys", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
def create_api_key(
    user: User = Depends(get_session_user),
    identities: IdentityRepository = Depends(get_identity_repository),
) -> ApiKeyCreated:
    key, raw = identities.create_api_key(user)
    payload = ApiKeyOut.model_validate(key)
    return ApiKeyCreated(**payload.model_dump(), key=raw)


@router.get("/api-keys")
def list_api_keys(
    user: User = Depends(get_session_user),
    identities: IdentityRepository = Depends(get_identity_repository),
) -> dict[str, list[ApiKeyOut]]:
    keys = identities.list_api_keys(user.org_id)
    return {"keys": [ApiKeyOut.model_validate(key) for key in keys]}


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_api_key(
    key_id: uuid.UUID,
    user: User = Depends(get_session_user),
    identities: IdentityRepository = Depends(get_identity_repository),
) -> None:
    revoked = identities.revoke_api_key(org_id=user.org_id, key_id=key_id)
    if revoked is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
