from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from memory_api.db.deps import (
    get_api_key_store,
    get_google_verifier,
    get_identity_repository,
    get_repository,
)
from memory_api.db.identity import InMemoryIdentityRepository
from memory_api.db.repository import InMemoryMemoryRepository
from memory_api.main import app
from memory_api.services.api_keys import InMemoryApiKeyStore
from memory_api.services.embedding import HashEmbedder, get_embedder
from memory_api.services.google_auth import GoogleClaims, GoogleTokenError


@dataclass
class FakeVerifier:
    claims: GoogleClaims | None = None

    def verify(self, id_token: str) -> GoogleClaims:
        if self.claims is None or id_token != "valid-google-token":
            raise GoogleTokenError("invalid token")
        return self.claims


@pytest.fixture
def verifier() -> FakeVerifier:
    return FakeVerifier(
        claims=GoogleClaims(google_id="gid-1", email="jayant@example.com", name="Jayant")
    )


@pytest.fixture
def identities() -> InMemoryIdentityRepository:
    return InMemoryIdentityRepository()


@pytest.fixture
def client(verifier: FakeVerifier, identities: InMemoryIdentityRepository) -> TestClient:
    app.dependency_overrides[get_google_verifier] = lambda: verifier
    app.dependency_overrides[get_identity_repository] = lambda: identities
    app.dependency_overrides[get_embedder] = lambda: HashEmbedder()
    app.dependency_overrides[get_repository] = lambda: InMemoryMemoryRepository()
    app.dependency_overrides[get_api_key_store] = lambda: InMemoryApiKeyStore()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_google_auth_rejects_invalid_token(client: TestClient) -> None:
    response = client.post("/auth/google", json={"id_token": "nope"})
    assert response.status_code == 401


def test_google_auth_issues_session_and_allows_key_management(client: TestClient) -> None:
    login = client.post("/auth/google", json={"id_token": "valid-google-token"})
    assert login.status_code == 200, login.text
    assert login.json()["user"]["email"] == "jayant@example.com"
    assert client.cookies.get("memoria_session")

    created = client.post("/api-keys")
    assert created.status_code == 201, created.text
    raw = created.json()["key"]
    assert raw.startswith("mem_")
    listed = client.get("/api-keys")
    assert listed.status_code == 200
    assert listed.json()["keys"][0]["key_last4"] == raw[-4:]
    assert "key" not in listed.json()["keys"][0]

    key_id = listed.json()["keys"][0]["id"]
    revoked = client.delete(f"/api-keys/{key_id}")
    assert revoked.status_code == 204
    listed_after = client.get("/api-keys")
    assert listed_after.json()["keys"][0]["revoked_at"] is not None


def test_auth_me_returns_user_and_org(client: TestClient) -> None:
    login = client.post("/auth/google", json={"id_token": "valid-google-token"})
    assert login.status_code == 200
    me = client.get("/auth/me")
    assert me.status_code == 200
    body = me.json()
    assert body["user"]["email"] == "jayant@example.com"
    assert body["org"]["name"].endswith("'s org")


def test_session_can_list_memories_without_counting_recall(
    client: TestClient, identities: InMemoryIdentityRepository
) -> None:
    from memory_api.db.models import MemoryType
    from memory_api.db.repository import InMemoryMemoryRepository
    from memory_api.main import app
    from memory_api.services.embedding import HashEmbedder, embed_text

    login = client.post("/auth/google", json={"id_token": "valid-google-token"})
    assert login.status_code == 200
    user = next(iter(identities._users_by_id.values()))
    repo = InMemoryMemoryRepository()
    repo.insert(
        org_id=user.org_id,
        session_id="s1",
        memory_type=MemoryType.semantic,
        content="We prefer pytest",
        embedding=embed_text("We prefer pytest", embedder=HashEmbedder()),
        importance=0.5,
        source_metadata={},
    )
    app.dependency_overrides[get_repository] = lambda: repo
    listed = client.get("/memories", params={"session_id": "s1", "memory_type": "semantic"})
    assert listed.status_code == 200
    assert listed.json()["memories"][0]["content"] == "We prefer pytest"
    assert listed.json()["memories"][0]["access_count"] == 0
