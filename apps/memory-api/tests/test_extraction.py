from memory_api.db.models import MemoryType
from memory_api.services.extraction import HeuristicExtractor


def test_heuristic_extracts_preferences_and_can_return_nothing() -> None:
    extractor = HeuristicExtractor()
    events = [
        {
            "event_type": "message",
            "payload": {"content": "We prefer pytest over unittest in this repo."},
        },
        {
            "event_type": "tool_call",
            "payload": {"tool": "ls", "content": "listed files"},
        },
    ]
    candidates = extractor.extract(events)
    assert len(candidates) == 1
    assert "pytest" in candidates[0].content
    assert candidates[0].memory_type == MemoryType.semantic


def test_heuristic_extracts_fixes_as_procedural() -> None:
    extractor = HeuristicExtractor()
    candidates = extractor.extract(
        [
            {
                "event_type": "diff",
                "payload": {"summary": "Fixed stale JWT by refreshing the session cookie."},
            }
        ]
    )
    assert len(candidates) == 1
    assert candidates[0].memory_type == MemoryType.procedural


def test_empty_batch_is_success() -> None:
    assert HeuristicExtractor().extract([]) == []
