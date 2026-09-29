import json
import uuid

import pytest
import structlog
from fastapi import Depends
from fastapi.testclient import TestClient

from memory_api.auth import get_org_scope, get_principal, get_session_user
from memory_api.db.deps import (
    get_api_key_store,
    get_graph_store,
    get_identity_repository,
    get_kv_store,
    get_rate_limiter,
    get_repository,
)
from memory_api.db.identity import InMemoryIdentityRepository
from memory_api.db.repository import InMemoryMemoryRepository
from memory_api.main import app
from memory_api.observability.logging import configure_logging
from memory_api.services.api_keys import InMemoryApiKeyStore, generate_api_key
from memory_api.services.embedding import HashEmbedder, get_embedder
from memory_api.services.google_auth import GoogleClaims
from memory_api.services.rate_limit import SlidingWindowRateLimiter
from memory_api.services.session_tokens import issue_session_token
from memory_api.stores.noop import NoOpGraphStore, NoOpKVStore


def _log_events(output: str, event: str) -> list[dict]:
    matched = []
    for line in output.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        payload = json.loads(line)
        if payload.get("event") == event:
            matched.append(payload)
    return matched


def _request_finished(output: str) -> list[dict]:
    return _log_events(output, "request_finished")


def _emit_handler_log() -> dict[str, bool]:
    structlog.get_logger().info("handler_seen")
    return {"ok": True}


@pytest.fixture
def logging_client() -> TestClient:
    identities = InMemoryIdentityRepository()
    user = identities.find_or_create_google_user(
        GoogleClaims(google_id="gid-log", email="log@example.com", name="Log")
    )
    keys = InMemoryApiKeyStore()
    principal_org = uuid.uuid4()
    scope_org = uuid.uuid4()
    principal_key = generate_api_key()
    scope_key = generate_api_key()
    keys.add(org_id=principal_org, raw_key=principal_key)
    keys.add(org_id=scope_org, raw_key=scope_key)
    app.dependency_overrides[get_identity_repository] = lambda: identities
    app.dependency_overrides[get_repository] = lambda: InMemoryMemoryRepository()
    app.dependency_overrides[get_embedder] = lambda: HashEmbedder()
    app.dependency_overrides[get_api_key_store] = lambda: keys
    app.dependency_overrides[get_kv_store] = lambda: NoOpKVStore()
    app.dependency_overrides[get_graph_store] = lambda: NoOpGraphStore()
    limiter = SlidingWindowRateLimiter(limit=1, window_seconds=60)
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    with TestClient(app) as client:
        client.session_user = user
        client.principal_key = principal_key
        client.principal_org = principal_org
        client.scope_key = scope_key
        client.scope_org = scope_org
        yield client
    app.dependency_overrides.clear()


def test_request_finished_logs_caller_org(logging_client: TestClient, capsys) -> None:
    capsys.readouterr()
    user = logging_client.session_user

    logging_client.cookies.set("memoria_session", issue_session_token(user))
    session = logging_client.get("/auth/me")
    logging_client.cookies.clear()
    assert session.status_code == 200
    session_lines = _request_finished(capsys.readouterr().out)
    assert len(session_lines) == 1
    assert session_lines[0]["org_id"] == str(user.org_id)

    created = logging_client.post(
        "/memories",
        headers={"Authorization": f"Bearer {logging_client.principal_key}"},
        json={"session_id": "s1", "memory_type": "semantic", "content": "from key"},
    )
    assert created.status_code == 201
    created_lines = _request_finished(capsys.readouterr().out)
    assert len(created_lines) == 1
    assert created_lines[0]["org_id"] == str(logging_client.principal_org)

    blocked = logging_client.post(
        "/memories",
        headers={"Authorization": f"Bearer {logging_client.principal_key}"},
        json={"session_id": "s1", "memory_type": "semantic", "content": "from key"},
    )
    assert blocked.status_code == 429
    blocked_lines = _request_finished(capsys.readouterr().out)
    assert len(blocked_lines) == 1
    assert blocked_lines[0]["org_id"] == str(logging_client.principal_org)

    listed = logging_client.get(
        "/memories",
        headers={"Authorization": f"Bearer {logging_client.scope_key}"},
    )
    assert listed.status_code == 200
    listed_lines = _request_finished(capsys.readouterr().out)
    assert len(listed_lines) == 1
    assert listed_lines[0]["org_id"] == str(logging_client.scope_org)

    scope_blocked = logging_client.get(
        "/memories",
        headers={"Authorization": f"Bearer {logging_client.scope_key}"},
    )
    assert scope_blocked.status_code == 429
    scope_blocked_lines = _request_finished(capsys.readouterr().out)
    assert len(scope_blocked_lines) == 1
    assert scope_blocked_lines[0]["org_id"] == str(logging_client.scope_org)


def test_handler_log_keeps_caller_org(logging_client: TestClient, capsys) -> None:
    installed: list[object] = []
    for path, dependency in (
        ("/__obs/session", get_session_user),
        ("/__obs/principal", get_principal),
        ("/__obs/scope", get_org_scope),
    ):
        app.add_api_route(
            path,
            _emit_handler_log,
            methods=["GET"],
            dependencies=[Depends(dependency)],
        )
        installed.append(app.router.routes[-1])

    def handler_org(output: str) -> str | None:
        lines = _log_events(output, "handler_seen")
        assert len(lines) == 1
        return lines[0]["org_id"]

    try:
        capsys.readouterr()
        user = logging_client.session_user
        logging_client.cookies.set("memoria_session", issue_session_token(user))
        session = logging_client.get("/__obs/session")
        logging_client.cookies.clear()
        assert session.status_code == 200
        assert handler_org(capsys.readouterr().out) == str(user.org_id)

        created = logging_client.get(
            "/__obs/principal",
            headers={"Authorization": f"Bearer {logging_client.principal_key}"},
        )
        assert created.status_code == 200
        assert handler_org(capsys.readouterr().out) == str(logging_client.principal_org)

        scoped = logging_client.get(
            "/__obs/scope",
            headers={"Authorization": f"Bearer {logging_client.scope_key}"},
        )
        assert scoped.status_code == 200
        assert handler_org(capsys.readouterr().out) == str(logging_client.scope_org)
    finally:
        for route in installed:
            app.router.routes.remove(route)


def test_log_drops_memory_text_and_secrets(capsys):
    configure_logging()
    log = structlog.get_logger()
    log.info(
        "search_done",
        content="user lives in Lisbon",
        api_key="mem_secret",
        duration_ms=12,
    )
    line = capsys.readouterr().out
    assert "Lisbon" not in line
    assert "mem_secret" not in line
    assert "duration_ms" in line
