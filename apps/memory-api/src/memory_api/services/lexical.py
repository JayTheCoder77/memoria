from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

_LEXICAL_SQL = text(
    """
    WITH query AS (
        SELECT websearch_to_tsquery('english', :q) AS tsq
    )
    SELECT memories.id,
           ts_rank_cd(memories.content_tsv, query.tsq) AS rank
    FROM memories
    CROSS JOIN query
    WHERE memories.org_id = :org_id
      AND memories.embedding_model = :embedding_model
      AND memories.content_tsv @@ query.tsq
      AND (
            CAST(:session_id AS text) IS NULL
            OR memories.session_id = CAST(:session_id AS text)
          )
      AND (
            CAST(:user_id AS text) IS NULL
            OR memories.user_id = CAST(:user_id AS text)
          )
      AND (
            CAST(:agent_id AS text) IS NULL
            OR memories.agent_id = CAST(:agent_id AS text)
          )
    ORDER BY rank DESC
    LIMIT :limit
    """
)


def lexical_search(
    session: Session,
    *,
    org_id: uuid.UUID,
    q: str,
    session_id: str | None,
    limit: int,
    embedding_model: str,
    user_id: str | None = None,
    agent_id: str | None = None,
) -> list[tuple[uuid.UUID, float]]:
    rows = session.execute(
        _LEXICAL_SQL,
        {
            "org_id": org_id,
            "q": q,
            "session_id": session_id,
            "limit": limit,
            "embedding_model": embedding_model,
            "user_id": user_id,
            "agent_id": agent_id,
        },
    ).all()
    peak = max((float(rank) for _memory_id, rank in rows), default=1.0)
    if peak <= 0:
        peak = 1.0
    return [(memory_id, float(rank) / peak) for memory_id, rank in rows]
