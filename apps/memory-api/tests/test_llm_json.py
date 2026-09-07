import httpx

from memory_api.services.llm_json import LlmProvider, complete_json


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_complete_json_uses_first_successful_provider() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if "openrouter" in str(request.url):
            return httpx.Response(429, json={"error": "rate"})
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"ok": true}'}}]},
        )

    payload = complete_json(
        [{"role": "user", "content": "hi"}],
        providers=[
            LlmProvider(
                api_key="or",
                base_url="https://openrouter.ai/api/v1",
                model="openai/gpt-4o-mini",
            ),
            LlmProvider(
                api_key="g",
                base_url="https://api.groq.com/openai/v1",
                model="llama-3.1-8b-instant",
            ),
        ],
        http=_client(handler),
    )
    assert payload == {"ok": True}
    assert any("openrouter" in url for url in seen)
    assert any("groq" in url for url in seen)


def test_complete_json_all_fail_returns_empty_object() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "no"})

    payload = complete_json(
        [{"role": "user", "content": "hi"}],
        providers=[
            LlmProvider(api_key="g", base_url="https://api.groq.com/openai/v1", model="x")
        ],
        http=_client(handler),
    )
    assert payload == {}


def test_complete_json_skips_empty_provider_list() -> None:
    assert complete_json([{"role": "user", "content": "hi"}], providers=[]) == {}
