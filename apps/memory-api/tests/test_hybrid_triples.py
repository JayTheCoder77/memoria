import httpx

from memory_api.services.hybrid_triples import enrich_hybrid_triples


def _llm_http(body: dict, status_code: int = 200) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=body)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_enrich_without_key_returns_empty_for_regex_fallback() -> None:
    kv, graph = enrich_hybrid_triples("We prefer pytest")
    assert kv == []
    assert graph == []


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
        api_key="sk-test",
        model="openai/gpt-4o-mini",
        http=http,
    )
    assert kv == [{"fact_type": "preference", "entity": "rust", "value": None}]
    assert graph == [{"subject": "user", "relation": "prefers", "object": "rust"}]


def test_enrich_llm_failure_returns_empty() -> None:
    http = _llm_http({"error": "nope"}, status_code=500)
    kv, graph = enrich_hybrid_triples(
        "We prefer pytest",
        api_key="sk-test",
        model="openai/gpt-4o-mini",
        http=http,
    )
    assert kv == []
    assert graph == []
