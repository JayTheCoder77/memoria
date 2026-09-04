import httpx

from memory_api.services.kv_candidates import derive_kv_candidates


def test_rules_prefer_phrase_without_api_key() -> None:
    keys = derive_kv_candidates("What language do they prefer typescript")
    assert ("preference", "typescript") in keys


def test_llm_parses_keys_from_completion() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"keys":[{"fact_type":"city","entity":"Lisbon"}]}'
                        }
                    }
                ]
            },
        )

    http = httpx.Client(transport=httpx.MockTransport(handler))
    keys = derive_kv_candidates("where do they live", api_key="sk-or-test", http=http)
    assert keys == [("city", "lisbon")]


def test_llm_error_falls_back_to_rules() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "nope"})

    http = httpx.Client(transport=httpx.MockTransport(handler))
    keys = derive_kv_candidates(
        "prefer typescript",
        api_key="sk-or-test",
        http=http,
    )
    assert ("preference", "typescript") in keys


def test_llm_malformed_keys_falls_back_to_rules() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": '{"keys":"invalid"}'}}
                ]
            },
        )

    http = httpx.Client(transport=httpx.MockTransport(handler))
    keys = derive_kv_candidates(
        "prefer typescript",
        api_key="sk-or-test",
        http=http,
    )
    assert ("preference", "typescript") in keys
