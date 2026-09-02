from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime

SEMANTIC_WEIGHT = 0.6
IMPORTANCE_WEIGHT = 0.2
RECENCY_WEIGHT = 0.2
HALF_LIFE_DAYS = 14.0


def estimate_tokens(text: str) -> int:
    return max(len(text) // 4, 1)


def recency_weight(
    created_at: datetime,
    *,
    now: datetime | None = None,
    half_life_days: float = HALF_LIFE_DAYS,
) -> float:
    current = now or datetime.now(UTC)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    age_days = max((current - created_at).total_seconds() / 86400.0, 0.0)
    return 0.5 ** (age_days / half_life_days)


def retrieval_score(
    *,
    similarity: float,
    importance: float,
    recency: float,
) -> float:
    return (
        SEMANTIC_WEIGHT * similarity
        + IMPORTANCE_WEIGHT * importance
        + RECENCY_WEIGHT * recency
    )


def truncate_to_token_budget[T](
    items: Sequence[T],
    budget: int,
    *,
    text_of: Callable[[T], str],
) -> list[T]:
    kept: list[T] = []
    used = 0
    for item in items:
        cost = estimate_tokens(text_of(item))
        if kept and used + cost > budget:
            break
        if not kept and cost > budget:
            kept.append(item)
            break
        kept.append(item)
        used += cost
    return kept
