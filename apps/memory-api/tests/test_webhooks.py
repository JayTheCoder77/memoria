from __future__ import annotations

import hashlib
import hmac
import json
import logging
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from memory_api.db.deps import get_api_key_store, get_graph_store, get_kv_store, get_repository
from memory_api.db.repository import InMemoryMemoryRepository
from memory_api.main import app
from memory_api.services.api_keys import InMemoryApiKeyStore, generate_api_key
from memory_api.services.embedding import HashEmbedder, get_embedder
from memory_api.services.webhooks import InMemoryWebhookStore, webhook_store_for
from memory_api.stores.graph import InMemoryGraphStore
from memory_api.stores.kv import InMemoryKVStore


@pytest.fixture
def repo() -> InMemoryMemoryRepository:
    return InMemoryMemoryRepository()


@pytest.fixture
def keys() -> InMemoryApiKeyStore:
    return InMemoryApiKeyStore()


@pytest.fixture
def org_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def raw_key(keys: InMemoryApiKeyStore, org_id: uuid.UUID) -> str:
    raw = generate_api_key()
    keys.add(org_id=org_id, raw_key=raw)
    return raw


@pytest.fixture
def client(repo: InMemoryMemoryRepository, keys: InMemoryApiKeyStore) -> TestClient:
    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[get_embedder] = lambda: HashEmbedder()
    app.dependency_overrides[get_api_key_store] = lambda: keys
    app.dependency_overrides[get_kv_store] = lambda: InMemoryKVStore()
    app.dependency_overrides[get_graph_store] = lambda: InMemoryGraphStore()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _auth(raw_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {raw_key}"}


@pytest.fixture(autouse=True)
def _public_webhook_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "memory_api.services.webhooks.resolve_webhook_host",
        lambda _host: ["1.1.1.1"],
    )


@pytest.mark.parametrize("address", ["127.0.0.1", "169.254.169.254"])
def test_hostname_resolving_to_non_global_address_is_rejected(
    client: TestClient, raw_key: str, monkeypatch: pytest.MonkeyPatch, address: str
) -> None:
    monkeypatch.setattr(
        "memory_api.services.webhooks.resolve_webhook_host",
        lambda _host: [address],
    )
    rejected = client.post(
        "/webhooks",
        headers=_auth(raw_key),
        json={"url": "https://metadata.google.internal/hook", "events": ["memory.written"]},
    )
    assert rejected.status_code == 422


def test_private_or_http_webhook_url_is_rejected(client: TestClient, raw_key: str) -> None:
    for url in (
        "http://hooks.example.com/memory",
        "https://10.1.2.3/hook",
        "https://127.0.0.1/hook",
        "https://192.168.1.9/hook",
        "https://169.254.1.1/hook",
        "https://localhost/hook",
    ):
        rejected = client.post(
            "/webhooks",
            headers=_auth(raw_key),
            json={"url": url, "events": ["memory.written"]},
        )
        assert rejected.status_code == 422, url


def test_public_https_webhook_returns_secret_once(client: TestClient, raw_key: str) -> None:
    registered = client.post(
        "/webhooks",
        headers=_auth(raw_key),
        json={"url": "https://hooks.example.com/memory", "events": ["memory.written"]},
    )
    assert registered.status_code == 201
    secret = registered.json()["secret"]
    assert isinstance(secret, str) and secret
    listed = client.get("/webhooks", headers=_auth(raw_key))
    assert listed.status_code == 200
    assert secret not in listed.text


def test_remember_posts_webhook_after_commit(
    client: TestClient, repo: InMemoryMemoryRepository, raw_key: str, org_id: uuid.UUID, monkeypatch
) -> None:
    events: list[str] = []

    class _Session(Session):
        def commit(self) -> None:
            events.append("commit")

        def get(self, *_args, **_kwargs):
            return None

    repo._session = _Session()
    store = InMemoryWebhookStore()
    store.create(
        org_id=org_id,
        url="https://hooks.example.com/memory",
        events=["memory.written"],
    )
    monkeypatch.setattr(
        "memory_api.routers.memories.webhook_store_for",
        lambda _repo: store,
    )

    def _post(*_args, **_kwargs):
        events.append("post")

        class _Response:
            def raise_for_status(self) -> None:
                request = httpx.Request("POST", "https://hooks.example.com/memory")
                response = httpx.Response(500, request=request)
                raise httpx.HTTPStatusError("500", request=request, response=response)

        return _Response()

    monkeypatch.setattr("memory_api.services.webhooks.httpx.post", _post)
    created = client.post(
        "/memories",
        headers=_auth(raw_key),
        json={
            "session_id": "hooks",
            "memory_type": "semantic",
            "content": "commit before delivery",
        },
    )
    assert created.status_code == 201
    assert events == ["commit", "post"]


def test_delivery_skips_a_host_that_resolves_to_a_private_address(
    client: TestClient,
    raw_key: str,
    org_id: uuid.UUID,
    repo: InMemoryMemoryRepository,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    seeded = webhook_store_for(repo).create(
        org_id=org_id,
        url="https://metadata.google.internal/hook",
        events=["memory.written"],
    )
    monkeypatch.setattr(
        "memory_api.services.webhooks.resolve_webhook_host",
        lambda _host: ["169.254.169.254"],
    )
    posted: list[str] = []
    monkeypatch.setattr(
        "memory_api.services.webhooks.httpx.post",
        lambda *_args, **_kwargs: posted.append("post"),
    )
    content = "delivery log must not include this memory text"
    with caplog.at_level(logging.ERROR):
        created = client.post(
            "/memories",
            headers=_auth(raw_key),
            json={
                "session_id": "hooks",
                "memory_type": "semantic",
                "content": content,
            },
        )
    assert created.status_code == 201
    assert posted == []
    assert content not in caplog.text
    assert str(org_id) in caplog.text
    assert str(seeded.id) in caplog.text


def test_webhook_receiver_records_signature_and_remember_returns_201_on_500(
    client: TestClient,
    raw_key: str,
    org_id: uuid.UUID,
    repo: InMemoryMemoryRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded: list[dict[str, object]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            recorded.append(
                {
                    "signature": self.headers.get("X-Memoria-Signature"),
                    "body": body,
                }
            )
            self.send_response(500)
            self.end_headers()

        def log_message(self, fmt: str, *args: object) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        monkeypatch.setattr(
            "memory_api.services.webhooks.public_https_webhook_url",
            lambda url: url,
        )
        seeded = webhook_store_for(repo).create(
            org_id=org_id,
            url=f"http://127.0.0.1:{port}/hook",
            events=["memory.written"],
        )
        secret = seeded.secret

        content = "webhook body must not include this memory text"
        created = client.post(
            "/memories",
            headers=_auth(raw_key),
            json={
                "session_id": "hooks",
                "memory_type": "semantic",
                "content": content,
                "user_id": "ada",
            },
        )
        assert created.status_code == 201
        memory = created.json()

        assert len(recorded) == 1
        body = recorded[0]["body"]
        assert isinstance(body, bytes)
        signature = recorded[0]["signature"]
        expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        assert signature == expected
        payload = json.loads(body)
        assert set(payload) == {"event", "memory_id", "org_id", "user_id"}
        assert payload["event"] == "memory.written"
        assert payload["memory_id"] == memory["id"]
        assert payload["org_id"] == memory["org_id"]
        assert payload["user_id"] == "ada"
        assert content not in body.decode()
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()
