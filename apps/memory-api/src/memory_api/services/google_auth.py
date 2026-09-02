from __future__ import annotations

from dataclasses import dataclass

from google.auth.transport.requests import Request
from google.oauth2 import id_token

from memory_api.config import settings


class GoogleTokenError(Exception):
    pass


@dataclass(frozen=True)
class GoogleClaims:
    google_id: str
    email: str
    name: str


class GoogleTokenVerifier:
    def verify(self, token: str) -> GoogleClaims:
        try:
            payload = id_token.verify_oauth2_token(
                token,
                Request(),
                audience=settings.google_client_id or None,
            )
        except Exception as exc:
            raise GoogleTokenError("invalid google token") from exc
        return GoogleClaims(
            google_id=str(payload["sub"]),
            email=str(payload["email"]),
            name=str(payload.get("name") or payload["email"]),
        )


def get_google_verifier() -> GoogleTokenVerifier:
    return GoogleTokenVerifier()
