import pytest

from memory_api.services.embedding import HashEmbedder, get_embedder


def test_hash_embedder_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("memory_api.config.settings.embedder", "hash")
    assert isinstance(get_embedder(), HashEmbedder)
