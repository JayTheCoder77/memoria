from datetime import UTC, datetime, timedelta

from memory_api.services.scoring import (
    estimate_tokens,
    recency_weight,
    retrieval_score,
    truncate_to_token_budget,
)


def test_recency_weight_decays_with_age() -> None:
    now = datetime(2026, 9, 2, tzinfo=UTC)
    fresh = recency_weight(now, now=now)
    old = recency_weight(now - timedelta(days=14), now=now)
    assert fresh == 1.0
    assert 0.4 < old < 0.6


def test_retrieval_score_prefers_similarity_then_importance_and_recency() -> None:
    similar = retrieval_score(similarity=0.9, importance=0.2, recency=0.2)
    important = retrieval_score(similarity=0.5, importance=0.9, recency=0.2)
    assert similar > important


def test_truncate_to_token_budget_keeps_prefix_within_budget() -> None:
    items = [
        {"content": "abcd" * 10, "id": "a"},
        {"content": "efgh" * 10, "id": "b"},
        {"content": "ijkl" * 10, "id": "c"},
    ]
    kept = truncate_to_token_budget(items, budget=25, text_of=lambda item: item["content"])
    assert [item["id"] for item in kept] == ["a", "b"]
    assert sum(estimate_tokens(item["content"]) for item in kept) <= 25
