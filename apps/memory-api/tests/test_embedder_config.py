import pytest

from memory_api.services.embedding import HashEmbedder, get_embedder


def test_hash_embedder_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("memory_api.config.settings.embedder", "hash")
    monkeypatch.setattr("memory_api.config.settings.env", "test")
    assert isinstance(get_embedder(), HashEmbedder)


def test_hash_embedder_rejected_outside_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("memory_api.config.settings.embedder", "hash")
    monkeypatch.setattr("memory_api.config.settings.env", "dev")
    with pytest.raises(RuntimeError, match="MEMORIA_EMBEDDER"):
        get_embedder()


def test_unknown_embedder_rejected_outside_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("memory_api.config.settings.embedder", "typo")
    monkeypatch.setattr("memory_api.config.settings.env", "dev")
    with pytest.raises(RuntimeError, match="MEMORIA_EMBEDDER"):
        get_embedder()


def test_app_startup_rejects_hash_outside_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient

    from memory_api.main import app

    monkeypatch.setattr("memory_api.config.settings.embedder", "hash")
    monkeypatch.setattr("memory_api.config.settings.env", "dev")
    monkeypatch.setattr("memory_api.config.settings.run_worker", False)
    with pytest.raises(RuntimeError, match="MEMORIA_EMBEDDER"):
        with TestClient(app):
            pass
