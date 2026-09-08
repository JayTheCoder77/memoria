from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import pytest
from memoria_cloud.errors import MemoriaAuthError, MemoriaError
from memoria_cloud.models import EmitResult, GraphEdge, KvFact, Memory, MemorySearchResult
from typer.testing import CliRunner

from memoria_cloud_cli import config as cfg
from memoria_cloud_cli.main import app

runner = CliRunner()


def _memory(**overrides: object) -> Memory:
    payload = dict(
        id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        org_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        session_id="s1",
        memory_type="semantic",
        content="We prefer pytest",
        importance=0.5,
        access_count=0,
        source_metadata={},
        created_at=datetime(2026, 9, 2, tzinfo=UTC),
        updated_at=None,
        last_accessed_at=None,
        score=0.9,
    )
    payload.update(overrides)
    return Memory.model_validate(payload)


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def remember(self, **kwargs: object) -> Memory:
        self.calls.append(("remember", kwargs))
        return _memory(content=str(kwargs["content"]), session_id=str(kwargs["session_id"]))

    def recall(self, **kwargs: object) -> MemorySearchResult:
        self.calls.append(("recall", kwargs))
        return MemorySearchResult(memories=[_memory()])

    def list_memories(self, **kwargs: object) -> MemorySearchResult:
        self.calls.append(("list_memories", kwargs))
        return MemorySearchResult(memories=[_memory()])

    def kv_facts(self, **kwargs: object) -> list[KvFact]:
        self.calls.append(("kv_facts", kwargs))
        return [
            KvFact(
                fact_type="prefers",
                entity="user",
                value="pytest",
                memory_id=_memory().id,
                importance=0.5,
            )
        ]

    def graph_edges(self, **kwargs: object) -> list[GraphEdge]:
        self.calls.append(("graph_edges", kwargs))
        return [
            GraphEdge(
                subject="user",
                relation="prefers",
                object="pytest",
                valid=True,
                valid_from=None,
                valid_to=None,
                confidence=1.0,
                memory_id=_memory().id,
            )
        ]

    def update(self, memory_id: str, **kwargs: object) -> Memory:
        self.calls.append(("update", {"memory_id": memory_id, **kwargs}))
        return _memory(content=str(kwargs.get("content") or "updated"))

    def forget(self, memory_id: str) -> None:
        self.calls.append(("forget", {"memory_id": memory_id}))

    def emit(self, **kwargs: object) -> EmitResult:
        self.calls.append(("emit", kwargs))
        return EmitResult(status="queued", id=str(uuid.uuid4()))

    def health(self) -> dict[str, str]:
        self.calls.append(("health", {}))
        return {"status": "ok"}


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeClient:
    client = FakeClient()
    monkeypatch.setattr(
        "memoria_cloud_cli.main.make_client",
        lambda **kwargs: client,
    )
    return client


def test_remember_requires_session(fake: FakeClient) -> None:
    result = runner.invoke(app, ["remember", "hello"])
    assert result.exit_code == 1
    assert fake.calls == []


def test_remember_and_recall(fake: FakeClient) -> None:
    remembered = runner.invoke(app, ["remember", "We prefer pytest", "--session", "s1"])
    assert remembered.exit_code == 0
    assert "remembered" in remembered.stdout
    recalled = runner.invoke(app, ["recall", "pytest", "--session", "s1", "--explain"])
    assert recalled.exit_code == 0
    assert "We prefer pytest" in recalled.stdout
    assert fake.calls[0][0] == "remember"
    assert fake.calls[1][1]["explain"] is True


def test_list_facts_graph_update_forget_emit_health(fake: FakeClient) -> None:
    assert runner.invoke(app, ["list", "--session", "s1"]).exit_code == 0
    assert runner.invoke(app, ["facts", "--limit", "10"]).exit_code == 0
    assert runner.invoke(app, ["graph", "--all"]).exit_code == 0
    memory_id = str(_memory().id)
    assert runner.invoke(app, ["update", memory_id, "--content", "new"]).exit_code == 0
    assert runner.invoke(app, ["forget", memory_id]).exit_code == 0
    emitted = runner.invoke(
        app,
        ["emit", "--session", "s1", "--payload", json.dumps({"content": "hi"})],
    )
    assert emitted.exit_code == 0
    assert runner.invoke(app, ["health"]).exit_code == 0
    names = [name for name, _ in fake.calls]
    assert names == [
        "list_memories",
        "kv_facts",
        "graph_edges",
        "update",
        "forget",
        "emit",
        "health",
    ]
    assert fake.calls[2][1]["valid_only"] is False


def test_auth_error_exits_2(monkeypatch: pytest.MonkeyPatch) -> None:
    class Boom:
        def health(self) -> dict[str, str]:
            raise MemoriaAuthError("Invalid or missing API key", status_code=401)

    monkeypatch.setattr("memoria_cloud_cli.main.make_client", lambda **kwargs: Boom())
    result = runner.invoke(app, ["health"])
    assert result.exit_code == 2


def test_api_error_exits_1(monkeypatch: pytest.MonkeyPatch) -> None:
    class Boom:
        def health(self) -> dict[str, str]:
            raise MemoriaError("nope", status_code=500)

    monkeypatch.setattr("memoria_cloud_cli.main.make_client", lambda **kwargs: Boom())
    result = runner.invoke(app, ["health"])
    assert result.exit_code == 1


def test_config_roundtrip(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "config.toml"
    monkeypatch.setattr(cfg, "CONFIG_PATH", path)
    monkeypatch.setattr(cfg, "CONFIG_DIR", tmp_path)
    shown = runner.invoke(app, ["config"])
    assert shown.exit_code == 0
    assert "(not set)" in shown.stdout
    written = runner.invoke(app, ["config", "--api-key", "mem_abcdefghijklmnop"])
    assert written.exit_code == 0
    assert "mem_…mnop" in written.stdout
    assert "mem_abcdefghijklmnop" not in written.stdout
    saved = cfg.load_file(path)
    assert saved.api_key == "mem_abcdefghijklmnop"


def test_invalid_payload_json(fake: FakeClient) -> None:
    result = runner.invoke(app, ["emit", "--session", "s1", "--payload", "not-json"])
    assert result.exit_code == 1
    assert fake.calls == []
