from memory_api.services.ingest import should_enqueue


def test_skips_noisy_tool_calls() -> None:
    assert should_enqueue("tool_call", {"tool": "read_file"}) is False
    assert should_enqueue("tool_call", {"tool": "grep"}) is False


def test_enqueues_important_noisy_tool_calls() -> None:
    assert should_enqueue("tool_call", {"tool": "read_file", "important": True}) is True


def test_enqueues_session_end_and_messages() -> None:
    assert should_enqueue("session_end", {}) is True
    assert should_enqueue("message", {"content": "hello"}) is True
    assert should_enqueue("tool_call", {"tool": "edit"}) is True
    assert should_enqueue("diff", {"summary": "fix auth"}) is True
