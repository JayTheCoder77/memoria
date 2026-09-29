from __future__ import annotations

import json
import time
import uuid

import httpx
import pytest
from memoria_adapter import MemoriaBenchAdapter

BENCH_ORG = "11111111-1111-1111-1111-111111111111"
PROFILE_TEXT = "Profile: Morgan lives in Austin"
HIT_CONTENT = "Hit: Morgan drinks coffee"


@pytest.fixture(autouse=True)
def _clear_process_freeze() -> None:
    MemoriaBenchAdapter._frozen.clear()
    yield
    MemoriaBenchAdapter._frozen.clear()


def _adapter(
    handler,
) -> tuple[MemoriaBenchAdapter, list[httpx.Request], httpx.Client]:
    seen: list[httpx.Request] = []

    def transport(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    http = httpx.Client(transport=httpx.MockTransport(transport), base_url="http://memory")
    adapter = MemoriaBenchAdapter(
        org_id=BENCH_ORG,
        api_key="mem_test",
        http=http,
    )
    return adapter, seen, http


def _assert_scoped(request: httpx.Request, *, user_id: str) -> None:
    body = _body(request)
    org_id = request.url.params.get("org_id") or body.get("org_id")
    scoped_user = request.url.params.get("user_id") or body.get("user_id")
    assert org_id == BENCH_ORG
    assert scoped_user == user_id
    assert request.headers["authorization"] == "Bearer mem_test"
    assert "mem_test" not in str(request.url)


def _body(request: httpx.Request) -> dict:
    if not request.content:
        return {}
    return json.loads(request.content)


def test_missing_org_id_is_rejected() -> None:
    with pytest.raises(ValueError, match="org_id"):
        MemoriaBenchAdapter(org_id="", api_key="mem_test")


def test_ingest_posts_one_event_and_waits_for_drain() -> None:
    drain_calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        _assert_scoped(request, user_id="morgan")
        if request.method == "POST" and request.url.path == "/events":
            return httpx.Response(202, json={"status": "queued", "id": str(uuid.uuid4())})
        if request.method == "GET" and request.url.path == "/events/drain":
            drain_calls["n"] += 1
            drained = drain_calls["n"] >= 2
            return httpx.Response(
                200,
                json={"drained": drained, "pending": 0 if drained else 1},
            )
        return httpx.Response(404, json={"detail": request.url.path})

    adapter, seen, _http = _adapter(handler)
    started = time.monotonic()
    adapter.ingest("morgan", "sess-1", "Morgan lives in Austin")
    elapsed = time.monotonic() - started

    posts = [item for item in seen if item.method == "POST" and item.url.path == "/events"]
    drains = [item for item in seen if item.method == "GET" and item.url.path == "/events/drain"]
    assert len(posts) == 1
    body = _body(posts[0])
    assert body["event_type"] == "message"
    assert body["user_id"] == "morgan"
    assert body["session_id"] == "sess-1"
    assert body["org_id"] == BENCH_ORG
    assert body["payload"]["content"] == "Morgan lives in Austin"
    assert seen.index(posts[0]) < seen.index(drains[0])
    assert drain_calls["n"] == 2
    assert drains[0].url.params["session_id"] == "sess-1"
    assert drains[0].url.params["user_id"] == "morgan"
    assert drains[0].url.params["org_id"] == BENCH_ORG
    assert elapsed < 1.0


def test_freeze_rejects_later_ingest() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        _assert_scoped(request, user_id="morgan")
        if request.method == "POST" and request.url.path == "/events":
            return httpx.Response(202, json={"status": "queued", "id": "evt-1"})
        if request.method == "GET" and request.url.path == "/events/drain":
            return httpx.Response(200, json={"drained": True, "pending": 0})
        return httpx.Response(404)

    adapter, seen, http = _adapter(handler)
    adapter.ingest("morgan", "sess-1", "first")
    adapter.freeze("morgan")
    other = MemoriaBenchAdapter(org_id=BENCH_ORG, api_key="mem_test", http=http)
    with pytest.raises(RuntimeError):
        other.ingest("morgan", "sess-2", "must not be written")

    posts = [item for item in seen if item.method == "POST"]
    assert len(posts) == 1
    assert _body(posts[0])["session_id"] == "sess-1"


def test_context_places_profile_text_before_search_hits() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        _assert_scoped(request, user_id="morgan")
        if request.method == "GET" and request.url.path == "/profile":
            assert request.url.params["token_budget"] == "2048"
            return httpx.Response(
                200,
                json={"text": PROFILE_TEXT, "static": [], "dynamic": []},
            )
        if request.method == "GET" and request.url.path == "/memories/search":
            assert request.url.params["q"] == "where does morgan live"
            assert request.url.params["token_budget"] == "2048"
            assert request.url.params["user_id"] == "morgan"
            return httpx.Response(
                200,
                json={
                    "memories": [
                        {"id": "mem-1", "content": HIT_CONTENT},
                        {"id": "mem-2", "content": "Hit: Morgan works remotely"},
                    ]
                },
            )
        return httpx.Response(404, json={"detail": request.url.path})

    adapter, seen, _http = _adapter(handler)
    result = adapter.context("morgan", "where does morgan live")

    assert "fact card" not in result.lower()
    assert result.index(PROFILE_TEXT) < result.index(HIT_CONTENT)
    assert result.index(HIT_CONTENT) < result.index("Hit: Morgan works remotely")
    paths = [item.url.path for item in seen]
    assert paths == ["/profile", "/memories/search"]


def test_reset_deletes_persona_memories_in_bench_org() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        _assert_scoped(request, user_id="alex")
        if request.method == "GET" and request.url.path == "/memories":
            assert request.url.params["user_id"] == "alex"
            assert request.url.params["org_id"] == BENCH_ORG
            return httpx.Response(
                200,
                json={
                    "memories": [
                        {"id": "mem-a", "content": "one"},
                        {"id": "mem-b", "content": "two"},
                    ]
                },
            )
        if request.method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(404, json={"detail": request.url.path})

    adapter, seen, _http = _adapter(handler)
    adapter.reset("alex")

    deletes = [item for item in seen if item.method == "DELETE"]
    assert [item.url.path for item in deletes] == ["/memories/mem-a", "/memories/mem-b"]
    assert all(item.url.params["org_id"] == BENCH_ORG for item in deletes)
    assert all(item.url.params["user_id"] == "alex" for item in deletes)
