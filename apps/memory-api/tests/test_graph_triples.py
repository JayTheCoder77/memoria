from memory_api.db.models import MemoryType
from memory_api.services.extraction import Candidate
from memory_api.services.graph_triples import resolve_graph_triples


def test_explicit_triples_win_over_heuristic() -> None:
    candidate = Candidate(
        content="Ava lives in Berlin.",
        memory_type=MemoryType.semantic,
        graph_triples=[
            {"subject": "ava", "relation": "lives_in", "object": "paris"},
        ],
    )
    triples = resolve_graph_triples(candidate)
    assert triples == [{"subject": "ava", "relation": "lives_in", "object": "paris"}]


def test_heuristic_lives_in_and_skips_probe() -> None:
    lives = Candidate(
        content="Ava lives in Berlin.",
        memory_type=MemoryType.semantic,
    )
    probe = Candidate(
        content="explain skeleton probe",
        memory_type=MemoryType.semantic,
    )
    triples = resolve_graph_triples(lives)
    assert any(
        t["subject"] == "user" and t["relation"] == "lives_in" and t["object"] == "berlin"
        for t in triples
    )
    assert resolve_graph_triples(probe) == []


def test_empty_fields_dropped_and_cap_applied(monkeypatch) -> None:
    from memory_api.config import settings

    monkeypatch.setattr(settings, "graph_max_edges_per_add", 2)
    candidate = Candidate(
        content="x",
        memory_type=MemoryType.semantic,
        graph_triples=[
            {"subject": "", "relation": "lives_in", "object": "x"},
            {"subject": "user", "relation": "prefers", "object": "a"},
            {"subject": "user", "relation": "prefers", "object": "b"},
            {"subject": "user", "relation": "prefers", "object": "c"},
        ],
    )
    triples = resolve_graph_triples(candidate)
    assert len(triples) == 2
    assert triples[0]["object"] == "a"
