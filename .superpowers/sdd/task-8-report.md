# Task 8 report: Columns and query filters

Status: DONE

Commit: `f73136a` feat: filter memories by user and agent

## What landed

Optional `user_id` and `agent_id` (strings, max 128, trimmed; blank becomes omitted) are stored on memories and copied through KV and graph fan-out. Search, list, lexical/FTS, KV, and graph all keep the existing `org_id` and `embedding_model` filters. A passed id must match. An omitted id does not filter, so existing callers still see every user in the org.

KV uniqueness is `(org_id, user_id, fact_type, entity)`. The migration backfills with `COALESCE(user_id, '')` and a single unique constraint. Null user ids are stored as `''`. There are no partial indexes.

Graph nodes use the same empty-string storage for both ids, and their unique key is `(org_id, user_id, agent_id, entity_key)`. That keeps two people, or two agents, from sharing a node and invalidating each other's edges. The brief only required the COALESCE unique key for KV; the graph key is the same idea so graph recall stays disjoint.

MCP `remember`, `recall`, and `emit`, and the SDK methods of the same names, take optional `user_id` and `agent_id` and do not require them. Emit forwards them on `POST /events`. The worker stamps them onto extracted memories. No profile endpoint was added.

## TDD evidence

### RED

Command (from `apps/memory-api`):

```bash
uv run pytest tests/test_scope_filters.py -v --tb=line
```

Result: 5 failed. Failures were the missing behavior, not setup errors.

- `test_ava_cannot_see_sams_memory_kv_fact_or_graph_edge_unless_user_id_omitted`: search with `user_id=ava` still returned Sam's memory (`assert '<id>' not in {'<id>'}`).
- `test_passed_agent_id_must_match_and_omitted_agent_id_does_not_filter`: `agent_id=retriever` still returned the planner memory.
- `test_user_id_is_trimmed_and_rejects_more_than_128_characters`: a 129-character `user_id` was accepted (`assert 201 == 422`).
- `test_two_users_can_store_the_same_kv_fact`: the second write overwrote the first (`assert {'helix'} == {'helix', 'vim'}`).
- `test_lexical_search_keeps_org_and_model_and_filters_user_and_agent`: lexical SQL had `org_id` and `embedding_model` and did not mention `memories.user_id`.

### GREEN

Command (step 4 of the brief):

```bash
uv run pytest tests/test_scope_filters.py tests/test_tenant_query_layer.py -v
```

Result: 6 passed.

Full memory-api suite, after `uv run alembic upgrade head` on the local database (the first full run failed only because `memories.user_id` was not migrated yet):

```bash
uv run pytest -q --tb=line
```

Result: 192 passed, 1 warning (pre-existing Starlette/`httpx` deprecation).

Also: SDK `uv run pytest tests/test_client.py` 6 passed; MCP `uv run pytest` 7 passed; `uv run ruff check` clean on memory-api, the SDK, and the MCP server.

## Files changed

- `apps/memory-api/alembic/versions/0011_scopes.py` (new; `revision = "0011_scopes"`, `down_revision = "0010_memory_fts"`)
- `apps/memory-api/src/memory_api/services/scope.py` (new trim/match helpers)
- `apps/memory-api/src/memory_api/db/models.py`
- `apps/memory-api/src/memory_api/db/repository.py`
- `apps/memory-api/src/memory_api/schemas/memory.py` (`MemoryCreate`, `MemorySearch`)
- `apps/memory-api/src/memory_api/schemas/event.py`
- `apps/memory-api/src/memory_api/routers/memories.py`
- `apps/memory-api/src/memory_api/routers/indexes.py` (KV and graph list filters; required so the visibility test can see facts and edges)
- `apps/memory-api/src/memory_api/routers/events.py`
- `apps/memory-api/src/memory_api/services/dedup.py`
- `apps/memory-api/src/memory_api/services/kv_fanout.py`
- `apps/memory-api/src/memory_api/services/graph_fanout.py`
- `apps/memory-api/src/memory_api/services/hybrid_search.py`
- `apps/memory-api/src/memory_api/services/lexical.py`
- `apps/memory-api/src/memory_api/services/worker.py`
- `apps/memory-api/src/memory_api/stores/kv.py`
- `apps/memory-api/src/memory_api/stores/graph.py`
- `apps/memory-api/src/memory_api/stores/vector.py`
- `apps/memory-api/src/memory_api/stores/noop.py`
- `apps/memory-api/src/memory_api/stores/protocols.py`
- `apps/memory-api/src/memory_api/stores/types.py`
- `apps/memory-api/tests/test_scope_filters.py` (new)
- `apps/memory-api/tests/test_stores.py` (column sets)
- `apps/mcp-server/src/mcp_server/server.py`
- `apps/mcp-server/tests/test_tools.py`
- `packages/memoria-cloud-sdk/src/memoria_cloud/client.py`
- `packages/memoria-cloud-sdk/tests/test_client.py`

`docs/` was left untracked. Shipped Alembic revisions were not edited.

## Self-review

- `org_id` stays mandatory. Scope ids are extra filters, not a substitute.
- Vector search still requires `embedding_model`. Lexical SQL still requires `org_id` and `embedding_model`, and adds the same optional user and agent predicates.
- Recall does not call an LLM. Scope is written at ingest and on `POST /memories`.
- Blank or whitespace-only ids are treated as omitted. Values longer than 128 characters are rejected with 422.
- Dedup merges only when `user_id` and `agent_id` are exactly equal, so a scoped write does not fold into another person's row. An omitted id on search still means all users.
- KV `agent_id` is not part of the unique key, matching the brief. A second agent writing the same `(org, user, fact_type, entity)` updates that one row, including its `agent_id`.
- Graph node uniqueness includes `agent_id` as well as `user_id`, both stored as `''` when omitted. That is wider than the KV rule in the brief, and it is what keeps graph edges from crossing users or agents.
