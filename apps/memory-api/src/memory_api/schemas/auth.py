from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class GoogleAuthRequest(BaseModel):
    id_token: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    org_id: uuid.UUID
    email: str
    name: str
    google_id: str


class OrgOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str


class OpenRouterOut(BaseModel):
    configured: bool
    last4: str | None = None
    model: str | None = None


class OpenRouterUpdate(BaseModel):
    api_key: str | None = None
    model: str | None = None


class MeOut(BaseModel):
    user: UserOut
    org: OrgOut
    openrouter: OpenRouterOut


class GoogleAuthResponse(BaseModel):
    token: str
    user: UserOut


class ApiKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key_last4: str
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None


class ApiKeyCreated(ApiKeyOut):
    key: str
