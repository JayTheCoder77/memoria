from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status

from memory_api.db.deps import get_api_key_store
from memory_api.services.api_keys import ApiKeyStore, AuthError, Principal, authenticate_bearer


def get_principal(
    authorization: str | None = Header(default=None),
    store: ApiKeyStore = Depends(get_api_key_store),
) -> Principal:
    try:
        return authenticate_bearer(authorization, store)
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        ) from exc
