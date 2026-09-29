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


def test_ingest_posts_one_event_and_polls_pending() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        _assert_scoped(request, user_id="morgan")
        if request.method == "POST" and request.url.path == "/events":
            return httpx.Response(202, json={"status": "queued", "id": str(uuid.uuid4())})
        if request.method == "GET" and request.url.path == "/events/pending":
            assert set(request.url.params) >= {"session_id", "user_id", "org_id"}
            return httpx.Response(200, json={"pending": 0})
        return httpx.Response(404, json={"detail": request.url.path})

    adapter, seen, _http = _adapter(handler)
    started = time.monotonic()
    adapter.ingest("morgan", "sess-1", "Morgan lives in Austin")
    elapsed = time.monotonic() - started

    posts = [item for item in seen if item.method == "POST" and item.url.path == "/events"]
    polls = [item for item in seen if item.method == "GET" and item.url.path == "/events/pending"]
    assert len(posts) == 2
    message, closed = (_body(posts[0]), _body(posts[1]))
    assert message["event_type"] == "message"
    assert message["user_id"] == "morgan"
    assert message["session_id"] == "sess-1"
    assert message["org_id"] == BENCH_ORG
    assert message["payload"]["content"] == "Morgan lives in Austin"
    assert closed["event_type"] == "session_end"
    assert closed["user_id"] == "morgan"
    assert closed["session_id"] == "sess-1"
    assert closed["org_id"] == BENCH_ORG
    assert "Morgan lives in Austin" not in posts[1].content.decode()
    assert seen.index(posts[0]) < seen.index(posts[1]) < seen.index(polls[0])
    assert len(polls) == 1
    assert polls[0].url.params["session_id"] == "sess-1"
    assert polls[0].url.params["user_id"] == "morgan"
    assert polls[0].url.params["org_id"] == BENCH_ORG
    assert not any(item.url.path == "/events/drain" for item in seen)
    assert elapsed < 1.0


def test_ingest_raises_when_pending_does_not_clear() -> None:
    clock = {"now": 0.0}

    def sleep(seconds: float) -> None:
        clock["now"] += seconds

    def handler(request: httpx.Request) -> httpx.Response:
        _assert_scoped(request, user_id="morgan")
        if request.method == "POST" and request.url.path == "/events":
            return httpx.Response(202, json={"status": "queued", "id": "evt-1"})
        if request.method == "GET" and request.url.path == "/events/pending":
            return httpx.Response(200, json={"pending": 1})
        return httpx.Response(404)

    _adapter_unused, _seen, http = _adapter(handler)
    adapter = MemoriaBenchAdapter(
        org_id=BENCH_ORG,
        api_key="mem_test",
        http=http,
        sleep=sleep,
        monotonic=lambda: clock["now"],
        poll_interval=0.2,
        poll_timeout=0.5,
    )
    with pytest.raises(RuntimeError, match="not drained") as raised:
        adapter.ingest("morgan", "sess-9", "still pending")
    assert "still pending" not in str(raised.value)
    assert clock["now"] >= 0.5


def test_freeze_rejects_later_ingest() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        _assert_scoped(request, user_id="morgan")
        if request.method == "POST" and request.url.path == "/events":
            return httpx.Response(202, json={"status": "queued", "id": "evt-1"})
        if request.method == "GET" and request.url.path == "/events/pending":
            return httpx.Response(200, json={"pending": 0})
        return httpx.Response(404)

    adapter, seen, http = _adapter(handler)
    adapter.ingest("morgan", "sess-1", "first")
    adapter.freeze("morgan")
    other = MemoriaBenchAdapter(org_id=BENCH_ORG, api_key="mem_test", http=http)
    with pytest.raises(RuntimeError):
        other.ingest("morgan", "sess-2", "must not be written")

    posts = [item for item in seen if item.method == "POST"]
    assert [(_body(item)["event_type"], _body(item)["session_id"]) for item in posts] == [
        ("message", "sess-1"),
        ("session_end", "sess-1"),
    ]


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


def test_reset_deletes_memories_kv_and_graph_for_persona() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        _assert_scoped(request, user_id="alex")
        if request.method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(404, json={"detail": request.url.path})

    adapter, seen, _http = _adapter(handler)
    adapter.reset("alex")

    deletes = [item for item in seen if item.method == "DELETE"]
    assert [item.url.path for item in deletes] == ["/memories", "/kv-facts", "/graph"]
    assert all(item.url.params["org_id"] == BENCH_ORG for item in deletes)
    assert all(item.url.params["user_id"] == "alex" for item in deletes)
    assert not any(item.method == "GET" for item in seen)
