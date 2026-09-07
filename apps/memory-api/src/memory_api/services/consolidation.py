from __future__ import annotations

import uuid

from memory_api.db.repository import MemoryRepository, _cosine_distance
from memory_api.stores.protocols import GraphStore

CONSOLIDATE_THRESHOLD = 0.85


def consolidate_session(
    *,
    repo: MemoryRepository,
    org_id: uuid.UUID,
    session_id: str,
    threshold: float = CONSOLIDATE_THRESHOLD,
    graph: GraphStore | None = None,
) -> int:
    rows = repo.list(org_id=org_id, session_id=session_id)
    merged = 0
    remaining = list(rows)
    index = 0
    while index < len(remaining):
        other = index + 1
        while other < len(remaining):
            left = remaining[index]
            right = remaining[other]
            similarity = 1.0 - _cosine_distance(left.embedding, right.embedding)
            if similarity >= threshold:
                if left.importance >= right.importance:
                    winner, loser = left, right
                else:
                    winner, loser = right, left
                winner.importance = max(left.importance, right.importance)
                if loser.content not in winner.content:
                    winner.content = f"{winner.content}\n{loser.content}"
                if graph is not None:
                    graph.reassign_memory(
                        org_id,
                        from_memory_id=loser.id,
                        to_memory_id=winner.id,
                    )
                repo.delete(org_id=org_id, memory_id=loser.id)
                remaining.pop(other)
                if winner is right:
                    remaining[index] = winner
                merged += 1
                continue
            other += 1
        index += 1
    return merged
