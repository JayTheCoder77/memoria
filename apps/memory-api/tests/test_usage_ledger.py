from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text
from sqlalchemy.exc import OperationalError

from memory_api.db.models import LlmUsage, Org
from memory_api.db.session import SessionLocal, engine
from memory_api.main import app
from memory_api.observability.usage import record_llm_usage
from memory_api.services.llm_json import LlmProvider, complete_json

MODEL = "ledger-test-model"
PROMPT = "secret prompt where does ava live"


def _postgres_available() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except OperationalError:
        return False


_needs_postgres = pytest.mark.skipif(
    not _postgres_available(), reason="Postgres is not running"
)


def _metrics_text(client: TestClient) -> str:
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    return response.text


def _counter_value(body: str, direction: str) -> float:
    needle = f'memoria_llm_tokens_total{{direction="{direction}",model="{MODEL}"}}'
    for line in body.splitlines():
        if line.startswith(needle):
            return float(line.split()[-1])
    return 0.0


def _histogram_count(body: str) -> float:
    prefix = "memoria_request_duration_seconds_count"
    for line in body.splitlines():
        if line.startswith(prefix):
            return float(line.split()[-1])
    return 0.0


def _create_org() -> uuid.UUID:
    org_id = uuid.uuid4()
    session = SessionLocal()
    try:
        session.add(Org(id=org_id, name="usage-ledger", created_at=datetime.now(UTC)))
        session.commit()
    finally:
        session.close()
    return org_id


def _usage_rows(org_id: uuid.UUID) -> list[LlmUsage]:
    session = SessionLocal()
    try:
        return list(
            session.scalars(select(LlmUsage).where(LlmUsage.org_id == org_id)).all()
        )
    finally:
        session.close()


def _delete_org(org_id: uuid.UUID) -> None:
    session = SessionLocal()
    try:
        session.execute(delete(LlmUsage).where(LlmUsage.org_id == org_id))
        org = session.get(Org, org_id)
        if org is not None:
            session.delete(org)
        session.commit()
    finally:
        session.close()


@_needs_postgres
def test_record_llm_usage_inserts_one_row_and_metrics_counter() -> None:
    org_id = _create_org()
    try:
        with TestClient(app) as client:
            before = _metrics_text(client)
            record_llm_usage(
                org_id=org_id,
                user_id=None,
                model=MODEL,
                input_tokens=11,
                output_tokens=7,
                duration_ms=12.5,
                trace_id="abc123",
            )
            rows = _usage_rows(org_id)
            assert len(rows) == 1
            row = rows[0]
            assert row.org_id == org_id
            assert row.user_id is None
            assert row.model == MODEL
            assert row.input_tokens == 11
            assert row.output_tokens == 7
            assert row.duration_ms == 12.5
            assert row.trace_id == "abc123"
            assert row.created_at is not None

            body = _metrics_text(client)
        assert _counter_value(body, "input") - _counter_value(before, "input") == 11
        assert _counter_value(body, "output") - _counter_value(before, "output") == 7
        assert PROMPT not in body
    finally:
        _delete_org(org_id)


@_needs_postgres
def test_provider_usage_is_stored_and_omitted_usage_is_zero() -> None:
    org_id = _create_org()
    long_content = "token " * 40

    def handler(request: httpx.Request) -> httpx.Response:
        if "with-usage" in str(request.url):
            return httpx.Response(
                200,
                json={
                    "usage": {"prompt_tokens": 4, "completion_tokens": 9},
                    "choices": [{"message": {"content": '{"ok": true}'}}],
                },
            )
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"ok": true}'}}]},
        )

    try:
        counted = complete_json(
            [{"role": "user", "content": long_content}],
            providers=[
                LlmProvider(
                    api_key="sk-test",
                    base_url="https://with-usage.invalid/v1",
                    model=MODEL,
                )
            ],
            http=httpx.Client(transport=httpx.MockTransport(handler)),
            org_id=org_id,
        )
        omitted = complete_json(
            [{"role": "user", "content": long_content}],
            providers=[
                LlmProvider(
                    api_key="sk-test",
                    base_url="https://no-usage.invalid/v1",
                    model=MODEL,
                )
            ],
            http=httpx.Client(transport=httpx.MockTransport(handler)),
            org_id=org_id,
            user_id=None,
        )
        assert counted == {"ok": True}
        assert omitted == {"ok": True}
        rows = sorted(_usage_rows(org_id), key=lambda row: (row.input_tokens, row.output_tokens))
        assert len(rows) == 2
        zero, counted_row = rows
        assert zero.input_tokens == 0
        assert zero.output_tokens == 0
        assert zero.user_id is None
        assert counted_row.input_tokens == 4
        assert counted_row.output_tokens == 9
        assert counted_row.input_tokens != len(long_content)
        body = _metrics_text(TestClient(app))
        assert long_content not in body
        assert "sk-test" not in body
    finally:
        _delete_org(org_id)


def test_metrics_scrape_request_duration_histogram() -> None:
    with TestClient(app) as client:
        before = _histogram_count(_metrics_text(client))
        health = client.get("/health")
        assert health.status_code == 200
        body = _metrics_text(client)
    assert "memoria_request_duration_seconds" in body
    assert _histogram_count(body) >= before + 1
