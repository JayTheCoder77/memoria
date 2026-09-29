import pytest


@pytest.fixture(autouse=True)
def memoria_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("memory_api.config.settings.env", "test")
