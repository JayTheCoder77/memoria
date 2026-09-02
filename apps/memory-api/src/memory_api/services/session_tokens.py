from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt

from memory_api.config import settings
from memory_api.db.models import User


class SessionTokenError(Exception):
    pass


def issue_session_token(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "org_id": str(user.org_id),
        "exp": datetime.now(UTC) + timedelta(minutes=settings.jwt_ttl_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_session_user_id(token: str) -> uuid.UUID:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return uuid.UUID(payload["sub"])
    except Exception as exc:
        raise SessionTokenError("invalid session") from exc
