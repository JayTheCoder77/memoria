import httpx
import pytest

from memory_api.services.embedding import (
    EMBEDDING_DIM,
    HashEmbedder,
    HuggingFaceEmbedder,
    get_embedder,
)


def _vector() -> list[float]:
    return [0.0] * (EMBEDDING_DIM - 1) + [1.0]


def test_hf_embedder_posts_to_inference_router() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers.get("authorization")
        seen["body"] = request.content
        return httpx.Response(200, json=_vector())

    embedder = HuggingFaceEmbedder(
        token="hf_test",
        model="sentence-transformers/all-MiniLM-L6-v2",
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    vector = embedder.embed("We prefer pytest")

    assert len(vector) == EMBEDDING_DIM
    assert abs(sum(v * v for v in vector) - 1.0) < 1e-6
    assert "hf-inference/models/sentence-transformers/all-MiniLM-L6-v2" in str(seen["url"])
    assert seen["authorization"] == "Bearer hf_test"


def test_hf_embedder_mean_pools_token_matrix() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        row = [1.0] + [0.0] * (EMBEDDING_DIM - 1)
        return httpx.Response(200, json=[row, row])

    embedder = HuggingFaceEmbedder(
        token="hf_test",
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    vector = embedder.embed("hello")
    assert len(vector) == EMBEDDING_DIM
    assert vector[0] == pytest.approx(1.0)


def test_hf_embedder_retries_then_succeeds_on_cold_start() -> None:
    calls = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503, json={"error": "loading"})
        return httpx.Response(200, json=_vector())

    embedder = HuggingFaceEmbedder(
        token="hf_test",
        http=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=lambda _seconds: None,
    )
    vector = embedder.embed("retry me")
    assert len(vector) == EMBEDDING_DIM
    assert calls["n"] == 3


def test_get_embedder_hf(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("memory_api.config.settings.embedder", "hf")
    monkeypatch.setattr("memory_api.config.settings.hf_token", "hf_test")
    embedder = get_embedder()
    assert isinstance(embedder, HuggingFaceEmbedder)


def test_get_embedder_default_is_still_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("memory_api.config.settings.embedder", "hash")
    assert isinstance(get_embedder(), HashEmbedder)
