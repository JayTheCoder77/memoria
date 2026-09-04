# Phase 2 Graph Store Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Postgres graph store with soft-invalidation, write fan-out, and 1–2 hop search union.

**Architecture:** Mirror Phase 1 KV: Alembic + ORM + InMemory/Postgres stores, resolve/persist helpers, wire remember/worker/search. Graph failures never fail remember or search.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, Postgres, pytest.

## Global Constraints

- Follow `spec/v2-phase2-graph-store.md` verbatim for names, defaults, scores (1.0 / 0.5), caps (8 edges, 12 seeds).
- `enable_graph` default **true**; `graph_max_edges_per_add` default **8**.
- Alembic `0006_graph` revises `0005_kv_facts`. ORM class for edges: `GraphEdgeRow`.
- Soft-invalidate: never DELETE; set `valid=false`, `valid_to=now()` on prior valid `(org, subject_id, relation)` then insert.
- Normalize keys/relations: strip + lowercase. Empty tokens skip writes.
- `memory_id` on edges must belong to the same `org_id` or skip.
- Fan-out and search errors: log and continue (savepoints on writes).
- `"explain skeleton probe"` emits zero graph triples.
- Heuristic subject is always `user`.
- Session-scoped search must not leak other sessions via graph-linked memories.
- Ruff I001: isort imports alphabetically. Do not commit `.superpowers/`.
- TDD: failing tests first. Work from repo root `/Users/jayant/projects/memoria`. Tests: `cd apps/memory-api && uv run pytest` (ignore postgres if DB down). Commit after each task.

---

### Task 1: Flag, migration, ORM, graph stores

**Files:**
- Modify: `apps/memory-api/src/memory_api/config.py`, `.env.example`, `tests/test_hybrid_config.py`, `db/models.py`, `stores/__init__.py`, `stores/noop.py`, `tests/test_stores.py`
- Create: `alembic/versions/0006_graph.py`, `stores/graph.py`
- Test: `tests/test_stores.py` (in-memory). Postgres round-trip in Task 4.

**Interfaces:**
- Produces: `InMemoryGraphStore`, `PostgresGraphStore`, `normalize_graph_token`, `memory_hops(...) -> dict[uuid.UUID, int]`

- [ ] **Step 1–4:** TDD config: `enable_graph is True`, `graph_max_edges_per_add == 8`. Rename hybrid flag test accordingly.

- [ ] **Step 3:** Migration mirrors spec SQL (server_default gen_random_uuid/now, jsonb `'{}'`). Indexes as spec. ORM `GraphNode`, `GraphEdgeRow` with UniqueConstraint `uq_graph_nodes_org_key`. Boolean `valid`. FK memory ON DELETE SET NULL.

- [ ] **Store tests (write first):**
  - `normalize_graph_token` strip/lower
  - InMemory: upsert_node same key returns same id; add_edge `ava lives_in berlin` then `ava lives_in munich` → neighbors(valid_only) only munich; neighbors(as_of=before_second, valid_only=False path via as_of) returns berlin edge with valid_to set
  - `memory_hops`: 1-hop memory_id maps to 1; two-hop chain maps far memory to 2
  - empty subject skipped (no edge)
  - org isolation
  - NoOpGraphStore.memory_hops returns `{}`

Implement BFS hops clamped to 1–2. `as_of` validity: `valid_from <= as_of and (valid_to is None or valid_to > as_of)`.

PostgresGraphStore: same semantics; ownership check on memory_id; expire stale ORM after invalidate if needed.

- [ ] **Step 5:** Commit `Add Postgres graph store with soft-invalidation.`

---

### Task 2: Resolve triples and persist fan-out; wire writes

**Files:**
- Create: `services/graph_triples.py`, `services/graph_fanout.py`, `tests/test_graph_triples.py`, `tests/test_graph_fanout.py`
- Modify: `extraction.py` Candidate + LLM prompt/parse; `schemas/memory.py` `graph_triples`; `db/deps.py` `get_graph_store`; `routers/memories.py` create_memory; `services/worker.py`; `worker.py`; `tests/test_extraction.py`, `tests/test_memories_api.py` (201 on graph put raise), `tests/test_worker.py`

**Interfaces:**
- `resolve_graph_triples(candidate) -> list[dict]` keys subject/relation/object
- `persist_graph_facts(*, graph, memory, candidate, session=None) -> None`

- [ ] Explicit triples win; heuristic `Ava lives in Berlin` → user/lives_in/berlin; probe → []; cap 8; empty fields dropped.
- [ ] persist writes heuristic edge; survives add_edge error; no-op when flag off; survives resolve error (inside try).
- [ ] LLM extractor parses optional graph_triples.
- [ ] create_memory passes graph_triples; persist after KV; inject get_graph_store in API tests.
- [ ] Worker tick passes PostgresGraphStore or NoOp.

- [ ] Commit `Fan out graph triples without failing remember.`

---

### Task 3: Seeds, search union, explain, as_of

**Files:**
- Create: `services/graph_seeds.py`, `tests/test_graph_seeds.py`
- Modify: `routers/memories.py` search (`as_of: datetime | None = None`); `tests/test_memories_api.py`

**Interfaces:**
- `derive_graph_seeds(q, *, api_key, model, http_client=None) -> list[str]`
- Search union field for graph_hops; `relevance = max(vector, kv or 0, graph_score or 0)` where graph_score is 1.0 or 0.5
- Close httpx client if created internally (same as kv_candidates)

- [ ] Rules: `prefer typescript` includes typescript; no api key.
- [ ] LLM parses entities; HTTP error and malformed JSON → rules.
- [ ] Search: graph-only hit (decoys fill vector over-fetch like KV test); explain sources graph + graph_hops 1; enable_graph false → null hops; session_id filters; 2-hop explain graph_hops 2 and lower relevance than an otherwise equal 1-hop if easy, or at least graph_score 0.5 via explain relevance.
- [ ] Graph search exception → vector+KV still 200.
- [ ] Reuse `_org_llm_key` for seeds (already swallows decrypt errors).

- [ ] Commit `Union graph-linked memories into search scoring.`

---

### Task 4: Postgres integration, docs, ruff

**Files:**
- Modify: `tests/test_postgres_api.py` (TRUNCATE include graph_edges, graph_nodes; add isolation + invalidation + union test)
- Modify: `spec/v2_extension_plan.md` tick Phase 2; `spec/03-architecture.md`

- [ ] Postgres tests skip if DB down. Truncate `graph_edges, graph_nodes, kv_facts, ...`
- [ ] Run `uv run ruff check src tests` and in-memory pytest. Fix I001.
- [ ] Commit `Document Phase 2 graph store and cover Postgres graph tests.`

---

## Self-review vs spec

Coverage: tables, store, soft-invalidate, as_of, triples, fan-out, search union, hop scores, explain, session scope, flag default, docs. No dashboard, no PATCH rewrite, no protocol change required beyond extra `memory_hops` on concrete stores + NoOp.
