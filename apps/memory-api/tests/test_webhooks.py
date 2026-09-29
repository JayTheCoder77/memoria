from __future__ import annotations

import hashlib
import hmac
import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from fastapi.testclient import TestClient

from memory_api.db.deps import get_api_key_store, get_graph_store, get_kv_store, get_repository
from memory_api.db.repository import InMemoryMemoryRepository
from memory_api.main import app
from memory_api.services.api_keys import InMemoryApiKeyStore, generate_api_key
from memory_api.services.embedding import HashEmbedder, get_embedder
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


def test_webhook_receiver_records_signature_and_remember_returns_201_on_500(
    client: TestClient, raw_key: str
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
        registered = client.post(
            "/webhooks",
            headers=_auth(raw_key),
            json={
                "url": f"http://127.0.0.1:{port}/hook",
                "events": ["memory.written"],
            },
        )
        assert registered.status_code == 201
        secret = registered.json()["secret"]
        assert isinstance(secret, str) and secret

        listed = client.get("/webhooks", headers=_auth(raw_key))
        assert listed.status_code == 200
        assert secret not in listed.text

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
