from __future__ import annotations

from fastapi import Cookie, Depends, Header, HTTPException, Request, status

from memory_api.config import settings
from memory_api.db.deps import get_api_key_store, get_identity_repository, get_rate_limiter
from memory_api.db.identity import IdentityRepository
from memory_api.db.models import User
from memory_api.services.api_keys import ApiKeyStore, AuthError, Principal, authenticate_bearer
from memory_api.services.rate_limit import RateLimitExceeded, SlidingWindowRateLimiter
from memory_api.services.session_tokens import SessionTokenError, decode_session_user_id


def get_principal(
    authorization: str | None = Header(default=None),
    store: ApiKeyStore = Depends(get_api_key_store),
    limiter: SlidingWindowRateLimiter = Depends(get_rate_limiter),
) -> Principal:
    try:
        principal = authenticate_bearer(authorization, store)
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        ) from exc
    try:
        limiter.hit(principal.api_key_id)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
        ) from exc
    return principal


def get_session_user(
    request: Request,
    authorization: str | None = Header(default=None),
    identities: IdentityRepository = Depends(get_identity_repository),
    memoria_session: str | None = Cookie(default=None, alias="memoria_session"),
) -> User:
    token = memoria_session or request.cookies.get(settings.session_cookie_name)
    if authorization and authorization.startswith("Bearer "):
        raw = authorization.removeprefix("Bearer ").strip()
        if not raw.startswith("mem_"):
            token = raw
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing session",
        )
    try:
        user_id = decode_session_user_id(token)
    except SessionTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing session",
        ) from exc
    user = identities.get_user(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing session",
        )
    return user
