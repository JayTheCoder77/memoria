from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator

from memory_api.auth import get_principal
from memory_api.db.deps import get_repository
from memory_api.db.repository import MemoryRepository
from memory_api.services.api_keys import Principal
from memory_api.services.webhooks import public_https_webhook_url, webhook_store_for

router = APIRouter()


class WebhookCreate(BaseModel):
    url: str
    events: list[str]

    @field_validator("url")
    @classmethod
    def _url(cls, value: str) -> str:
        return public_https_webhook_url(value)

    @field_validator("events")
    @classmethod
    def _events(cls, value: list[str]) -> list[str]:
        if not value or any(not isinstance(item, str) or not item.strip() for item in value):
            raise ValueError("events must be a non-empty list of event names")
        return value


class WebhookCreated(BaseModel):
    id: uuid.UUID
    url: str
    events: list[str]
    secret: str


class WebhookOut(BaseModel):
    id: uuid.UUID
    url: str
    events: list[str]


class WebhookList(BaseModel):
    webhooks: list[WebhookOut]


@router.post("/webhooks", response_model=WebhookCreated, status_code=status.HTTP_201_CREATED)
def create_webhook(
    body: WebhookCreate,
    principal: Principal = Depends(get_principal),
    repo: MemoryRepository = Depends(get_repository),
) -> WebhookCreated:
    if principal.api_key_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    record = webhook_store_for(repo).create(
        org_id=principal.org_id,
        url=body.url,
        events=body.events,
    )
    return WebhookCreated(
        id=record.id,
        url=record.url,
        events=record.events,
        secret=record.secret,
    )


@router.get("/webhooks", response_model=WebhookList)
def list_webhooks(
    principal: Principal = Depends(get_principal),
    repo: MemoryRepository = Depends(get_repository),
) -> WebhookList:
    rows = webhook_store_for(repo).list(principal.org_id)
    return WebhookList(
        webhooks=[
            WebhookOut(id=row.id, url=row.url, events=row.events) for row in rows
        ]
    )
