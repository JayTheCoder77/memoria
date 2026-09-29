from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import logging
import secrets
import socket
import uuid
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from memory_api.db.models import WebhookEndpoint
from memory_api.db.repository import MemoryRepository

logger = logging.getLogger(__name__)

_DELIVERY_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class WebhookEndpointRecord:
    id: uuid.UUID
    org_id: uuid.UUID
    url: str
    events: list[str]
    secret: str


class WebhookStore(Protocol):
    def create(
        self, *, org_id: uuid.UUID, url: str, events: list[str]
    ) -> WebhookEndpointRecord: ...

    def list(self, org_id: uuid.UUID) -> list[WebhookEndpointRecord]: ...

    def for_event(self, org_id: uuid.UUID, event: str) -> list[WebhookEndpointRecord]: ...


def _record(row: WebhookEndpoint) -> WebhookEndpointRecord:
    events = row.events if isinstance(row.events, list) else []
    return WebhookEndpointRecord(
        id=row.id,
        org_id=row.org_id,
        url=row.url,
        events=[item for item in events if isinstance(item, str)],
        secret=row.secret,
    )


class InMemoryWebhookStore:
    def __init__(self) -> None:
        self._rows: list[WebhookEndpointRecord] = []

    def create(
        self, *, org_id: uuid.UUID, url: str, events: list[str]
    ) -> WebhookEndpointRecord:
        record = WebhookEndpointRecord(
            id=uuid.uuid4(),
            org_id=org_id,
            url=url,
            events=list(events),
            secret=secrets.token_urlsafe(32),
        )
        self._rows.append(record)
        return record

    def list(self, org_id: uuid.UUID) -> list[WebhookEndpointRecord]:
        return [row for row in self._rows if row.org_id == org_id]

    def for_event(self, org_id: uuid.UUID, event: str) -> list[WebhookEndpointRecord]:
        return [row for row in self.list(org_id) if event in row.events]


class PostgresWebhookStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self, *, org_id: uuid.UUID, url: str, events: list[str]
    ) -> WebhookEndpointRecord:
        row = WebhookEndpoint(
            org_id=org_id,
            url=url,
            events=list(events),
            secret=secrets.token_urlsafe(32),
        )
        self._session.add(row)
        self._session.flush()
        return _record(row)

    def list(self, org_id: uuid.UUID) -> list[WebhookEndpointRecord]:
        rows = self._session.scalars(
            select(WebhookEndpoint).where(WebhookEndpoint.org_id == org_id)
        )
        return [_record(row) for row in rows]

    def for_event(self, org_id: uuid.UUID, event: str) -> list[WebhookEndpointRecord]:
        # A failed lookup must not abort the caller's transaction (remember still commits).
        with self._session.begin_nested():
            rows = list(
                self._session.scalars(
                    select(WebhookEndpoint).where(
                        WebhookEndpoint.org_id == org_id,
                        WebhookEndpoint.events.contains([event]),
                    )
                )
            )
        return [_record(row) for row in rows]


_in_memory_webhooks = InMemoryWebhookStore()


def webhook_store_for(repo: MemoryRepository) -> WebhookStore:
    session = getattr(repo, "_session", None)
    if session is None:
        return _in_memory_webhooks
    return PostgresWebhookStore(session)


class WebhookURLError(ValueError):
    pass


def _blocked_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    mapped = getattr(address, "ipv4_mapped", None)
    if mapped is not None and _blocked_address(mapped):
        return True
    return not address.is_global


def resolve_webhook_host(host: str) -> list[str]:
    infos = socket.getaddrinfo(host, None)
    return [str(sockaddr[0]).split("%", 1)[0] for *_, sockaddr in infos]


def _resolved_addresses(host: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        return [ipaddress.ip_address(host)]
    except ValueError:
        pass
    try:
        raw_addresses = resolve_webhook_host(host)
    except OSError as exc:
        raise WebhookURLError("webhook host did not resolve") from exc
    if not raw_addresses:
        raise WebhookURLError("webhook host did not resolve")
    return [ipaddress.ip_address(ip) for ip in raw_addresses]


def public_https_webhook_url(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or not host or host == "localhost" or host.endswith(".localhost"):
        raise WebhookURLError("url must be a public https address")
    for address in _resolved_addresses(host):
        if _blocked_address(address):
            raise WebhookURLError("url must be a public https address")
    return url


@dataclass(frozen=True)
class PendingWebhook:
    org_id: uuid.UUID
    webhook_id: uuid.UUID
    url: str
    secret: str
    body: bytes


def collect_memory_written(
    store: WebhookStore,
    *,
    memory_id: uuid.UUID,
    org_id: uuid.UUID,
    user_id: str | None,
) -> list[PendingWebhook]:
    try:
        endpoints = store.for_event(org_id, "memory.written")
    except Exception:
        logger.error("webhook lookup failed org_id=%s", org_id)
        return []
    body = memory_written_body(memory_id=memory_id, org_id=org_id, user_id=user_id)
    return [
        PendingWebhook(
            org_id=org_id,
            webhook_id=endpoint.id,
            url=endpoint.url,
            secret=endpoint.secret,
            body=body,
        )
        for endpoint in endpoints
    ]


def post_webhooks(pending: list[PendingWebhook]) -> None:
    for item in pending:
        try:
            public_https_webhook_url(item.url)
        except Exception as exc:
            logger.error(
                "webhook delivery failed org_id=%s webhook_id=%s error=%s",
                item.org_id,
                item.webhook_id,
                type(exc).__name__,
            )
            continue
        try:
            response = httpx.post(
                item.url,
                content=item.body,
                headers={
                    "Content-Type": "application/json",
                    "X-Memoria-Signature": sign_body(item.secret, item.body),
                },
                timeout=_DELIVERY_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except Exception as exc:
            logger.error(
                "webhook delivery failed org_id=%s webhook_id=%s error=%s",
                item.org_id,
                item.webhook_id,
                type(exc).__name__,
            )


def sign_body(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def memory_written_body(
    *,
    memory_id: uuid.UUID,
    org_id: uuid.UUID,
    user_id: str | None,
) -> bytes:
    payload = {
        "event": "memory.written",
        "memory_id": str(memory_id),
        "org_id": str(org_id),
        "user_id": user_id,
    }
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def deliver_memory_written(
    store: WebhookStore,
    *,
    memory_id: uuid.UUID,
    org_id: uuid.UUID,
    user_id: str | None,
) -> None:
    post_webhooks(
        collect_memory_written(
            store,
            memory_id=memory_id,
            org_id=org_id,
            user_id=user_id,
        )
    )
