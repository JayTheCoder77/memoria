from memory_api.db.models import MemoryType
from memory_api.services.extraction import Candidate
from memory_api.services.kv_triples import resolve_kv_triples


def test_explicit_triples_win_over_heuristic() -> None:
    candidate = Candidate(
        content="We prefer pytest over unittest in this repo.",
        memory_type=MemoryType.semantic,
        kv_triples=[{"fact_type": "language", "entity": "python", "value": None}],
    )
    triples = resolve_kv_triples(candidate)
    assert triples == [{"fact_type": "language", "entity": "python", "value": None}]


def test_heuristic_preference_and_skips_probe() -> None:
    prefer = Candidate(
        content="We prefer pytest over unittest in this repo.",
        memory_type=MemoryType.semantic,
    )
    probe = Candidate(
        content="explain skeleton probe",
        memory_type=MemoryType.semantic,
    )
    triples = resolve_kv_triples(prefer)
    assert any(t["fact_type"] == "preference" and t["entity"] == "pytest" for t in triples)
    assert resolve_kv_triples(probe) == []


def test_empty_type_or_entity_dropped_and_cap_applied(monkeypatch) -> None:
    from memory_api.config import settings

    monkeypatch.setattr(settings, "kv_max_triples_per_add", 2)
    candidate = Candidate(
        content="x",
        memory_type=MemoryType.semantic,
        kv_triples=[
            {"fact_type": "", "entity": "x"},
            {"fact_type": "a", "entity": "1"},
            {"fact_type": "b", "entity": "2"},
            {"fact_type": "c", "entity": "3"},
        ],
    )
    triples = resolve_kv_triples(candidate)
    assert len(triples) == 2
    assert triples[0]["entity"] == "1"
