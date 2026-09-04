import httpx

from memory_api.db.models import MemoryType
from memory_api.services.extraction import HeuristicExtractor, LlmExtractor, get_extractor


def test_heuristic_extracts_preferences_and_can_return_nothing() -> None:
    extractor = HeuristicExtractor()
    events = [
        {
            "event_type": "message",
            "payload": {"content": "We prefer pytest over unittest in this repo."},
        },
        {
            "event_type": "tool_call",
            "payload": {"tool": "ls", "content": "listed files"},
        },
    ]
    candidates = extractor.extract(events)
    assert len(candidates) == 1
    assert "pytest" in candidates[0].content
    assert candidates[0].memory_type == MemoryType.semantic


def test_heuristic_extracts_fixes_as_procedural() -> None:
    extractor = HeuristicExtractor()
    candidates = extractor.extract(
        [
            {
                "event_type": "diff",
                "payload": {"summary": "Fixed stale JWT by refreshing the session cookie."},
            }
        ]
    )
    assert len(candidates) == 1
    assert candidates[0].memory_type == MemoryType.procedural


def test_empty_batch_is_success() -> None:
    assert HeuristicExtractor().extract([]) == []


def _llm_http(body: dict) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_llm_extractor_parses_kv_triples_from_chat_completion() -> None:
    http = _llm_http(
        {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"memories":[{"content":"Prefer pytest.",'
                            '"memory_type":"semantic","importance":0.8,'
                            '"kv_triples":[{"fact_type":"preference","entity":"pytest"}]}]}'
                        )
                    }
                }
            ]
        }
    )
    extractor = LlmExtractor(
        api_key="sk-or-test",
        model="openai/gpt-4o-mini",
        base_url="https://openrouter.ai/api/v1",
        http=http,
    )
    candidates = extractor.extract(
        [{"event_type": "message", "payload": {"content": "We prefer pytest."}}]
    )
    assert len(candidates) == 1
    assert candidates[0].kv_triples[0]["entity"] == "pytest"


def test_llm_extractor_parses_memories_from_chat_completion() -> None:
    http = _llm_http(
        {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"memories":[{"content":"Prefer pytest.",'
                            '"memory_type":"semantic","importance":0.8}]}'
                        )
                    }
                }
            ]
        }
    )
    extractor = LlmExtractor(
        api_key="sk-or-test",
        model="openai/gpt-4o-mini",
        base_url="https://openrouter.ai/api/v1",
        http=http,
    )
    candidates = extractor.extract(
        [{"event_type": "message", "payload": {"content": "We prefer pytest."}}]
    )
    assert len(candidates) == 1
    assert candidates[0].content == "Prefer pytest."
    assert candidates[0].memory_type == MemoryType.semantic
    assert candidates[0].importance == 0.8
    assert candidates[0].source_metadata["extractor"] == "llm"


def test_llm_extractor_empty_list_is_success() -> None:
    http = _llm_http({"choices": [{"message": {"content": '{"memories":[]}'}}]})
    extractor = LlmExtractor(api_key="sk-or-test", model="openai/gpt-4o-mini", http=http)
    assert extractor.extract([{"event_type": "message", "payload": {"content": "ok"}}]) == []


def test_llm_extractor_calls_openrouter_with_byok_headers() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers.get("authorization", "")
        seen["http-referer"] = request.headers.get("http-referer", "")
        seen["x-title"] = request.headers.get("x-title", "")
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"memories":[]}'}}]})

    extractor = LlmExtractor(
        api_key="sk-or-v1-user",
        model="openai/gpt-4o-mini",
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    extractor.extract([{"event_type": "message", "payload": {"content": "prefer bun"}}])
    assert seen["url"].startswith("https://openrouter.ai/api/v1/chat/completions")
    assert seen["authorization"] == "Bearer sk-or-v1-user"
    assert seen["http-referer"]
    assert seen["x-title"] == "Memoria"


def test_get_extractor_is_heuristic_without_org_key() -> None:
    assert isinstance(get_extractor(), HeuristicExtractor)
    assert isinstance(get_extractor(api_key=None), HeuristicExtractor)


def test_get_extractor_uses_org_openrouter_key() -> None:
    extractor = get_extractor(api_key="sk-or-v1-user", model="anthropic/claude-sonnet-4")
    assert isinstance(extractor, LlmExtractor)
    assert extractor._api_key == "sk-or-v1-user"
    assert extractor._model == "anthropic/claude-sonnet-4"
    assert extractor._base_url == "https://openrouter.ai/api/v1"
