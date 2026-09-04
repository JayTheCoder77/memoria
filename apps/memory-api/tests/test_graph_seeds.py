import httpx

from memory_api.services.graph_seeds import derive_graph_seeds


def test_rules_prefer_phrase_without_api_key() -> None:
    seeds = derive_graph_seeds("What language do they prefer typescript")
    assert "typescript" in seeds


def test_llm_parses_entities_from_completion() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"entities":["Lisbon","user"]}'
                        }
                    }
                ]
            },
        )

    http = httpx.Client(transport=httpx.MockTransport(handler))
    seeds = derive_graph_seeds("where do they live", api_key="sk-or-test", http_client=http)
    assert seeds == ["lisbon", "user"]


def test_llm_error_falls_back_to_rules() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "nope"})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    seeds = derive_graph_seeds(
        "prefer typescript",
        api_key="sk-or-test",
        http_client=http,
    )
    assert "typescript" in seeds


def test_llm_malformed_entities_falls_back_to_rules() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": '{"entities":"invalid"}'}}
                ]
            },
        )

    http = httpx.Client(transport=httpx.MockTransport(handler))
    seeds = derive_graph_seeds(
        "prefer typescript",
        api_key="sk-or-test",
        http_client=http,
    )
    assert "typescript" in seeds
