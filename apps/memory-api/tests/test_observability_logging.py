import structlog

from memory_api.observability.logging import configure_logging


def test_log_drops_memory_text_and_secrets(capsys):
    configure_logging()
    log = structlog.get_logger()
    log.info(
        "search_done",
        content="user lives in Lisbon",
        api_key="mem_secret",
        duration_ms=12,
    )
    line = capsys.readouterr().out
    assert "Lisbon" not in line
    assert "mem_secret" not in line
    assert "duration_ms" in line
