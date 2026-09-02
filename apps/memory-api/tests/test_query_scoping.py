from __future__ import annotations

import uuid

from memory_api.db.repository import search_statement
from memory_api.services.embedding import EMBEDDING_DIM


def test_search_statement_requires_org_id_in_where_clause() -> None:
    org_id = uuid.uuid4()
    other_org = uuid.uuid4()
    stmt = search_statement(
        org_id=org_id,
        query_embedding=[0.0] * EMBEDDING_DIM,
        session_id="repo-memoria",
        limit=5,
    )
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": False}))

    assert "memories.org_id" in compiled
    assert "memories.session_id" in compiled
    params = stmt.compile().params
    assert org_id in params.values()
    assert other_org not in params.values()
