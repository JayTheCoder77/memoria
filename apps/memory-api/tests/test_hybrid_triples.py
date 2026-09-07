import httpx

from memory_api.services.hybrid_triples import enrich_hybrid_triples
from memory_api.services.llm_json import LlmProvider


def _llm_http(body: dict, status_code: int = 200) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=body)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_enrich_without_providers_returns_empty() -> None:
    assert enrich_hybrid_triples("We prefer pytest") == ([], [])


def test_enrich_parses_kv_and_graph_from_chat_completion() -> None:
    http = _llm_http(
        {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"kv_triples":[{"fact_type":"preference","entity":"rust","value":null}],'
                            '"graph_triples":[{"subject":"user","relation":"prefers","object":"rust"}]}'
                        )
                    }
                }
            ]
        }
    )
    kv, graph = enrich_hybrid_triples(
        "I like rust",
        providers=[
            LlmProvider(
                api_key="sk-test",
                base_url="https://openrouter.ai/api/v1",
                model="openai/gpt-4o-mini",
            )
        ],
        http=http,
    )
    assert kv == [{"fact_type": "preference", "entity": "rust", "value": None}]
    assert graph == [{"subject": "user", "relation": "prefers", "object": "rust"}]


def test_enrich_llm_failure_returns_empty() -> None:
    http = _llm_http({"error": "nope"}, status_code=500)
    kv, graph = enrich_hybrid_triples(
        "We prefer pytest",
        providers=[
            LlmProvider(
                api_key="sk-test",
                base_url="https://openrouter.ai/api/v1",
                model="openai/gpt-4o-mini",
            )
        ],
        http=http,
    )
    assert kv == []
    assert graph == []


def test_enrich_openrouter_429_then_groq() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "openrouter" in str(request.url):
            return httpx.Response(429, json={"error": "rate"})
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"kv_triples":[{"fact_type":"preference","entity":"rust","value":null}],'
                                '"graph_triples":[{"subject":"user","relation":"prefers","object":"rust"}]}'
                            )
                        }
                    }
                ]
            },
        )

    kv, graph = enrich_hybrid_triples(
        "I like rust",
        providers=[
            LlmProvider(api_key="or", base_url="https://openrouter.ai/api/v1", model="x"),
            LlmProvider(
                api_key="g",
                base_url="https://api.groq.com/openai/v1",
                model="openai/gpt-oss-20b",
            ),
        ],
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert kv[0]["entity"] == "rust"
    assert graph[0]["object"] == "rust"
