# Phase 3 Unified Fusion Retrieval Implementation Plan

> **For agentic workers:** Lean process: implement task-by-task with TDD. Main-thread diff review. No per-task reviewer agents.

**Goal:** Parallel HybridRetriever for search with frozen ranking, explain timings, and query-class benchmarks.

**Architecture:** Move search logic from `routers/memories.py` into `services/hybrid_search.py`. Fan out Vector/KV/Graph with a thread pool. Isolated SQLAlchemy sessions only for Postgres-backed stores. Router constructs the retriever and maps hits to `MemoryOut`.

**Tech Stack:** FastAPI, SQLAlchemy 2, pytest, `concurrent.futures`.

## Global Constraints

- Ranking freeze: do not change `relevance` / hop scores / fusion weights.
- Session-scoped search must not leak other sessions.
- Store failures: log and continue.
- `"explain skeleton probe"` still writes no KV/graph triples.
- Ruff I001 / E501. Do not commit `.superpowers/`.
- TDD: failing tests first. Work from `/Users/jayant/projects/memoria`. Tests: `cd apps/memory-api && uv run pytest` (skip postgres if DB down).
- Do not edit `.cursor/plans/`.

---

### Task 1: HybridRetriever extract (ranking freeze)

**Files:**
- Create: `apps/memory-api/src/memory_api/services/hybrid_search.py`, `apps/memory-api/tests/test_hybrid_search.py`
- Modify: `stores/protocols.py` (`memory_hops` on `GraphStore`), `db/deps.py` (`get_vector_store`), `routers/memories.py` (delegate search), `tests/test_memories_api.py` if `get_vector_store` must be overridden (prefer depending on `get_repository` so existing overrides work)

**Behavior:** Retriever owns embed + union + score + truncate. May still run stores sequentially in this task; Task 2 adds threads.

---

### Task 2: Parallel fan-out + isolated sessions

**Files:** `hybrid_search.py`, `test_hybrid_search.py`

- `ThreadPoolExecutor(max_workers=3)`.
- If KV/graph/vector are Postgres-backed, each worker `SessionLocal()` → store → read → close. Else use injected stores.
- Overlap test via start/end timestamps.
- Raising vector/KV/graph isolated.

---

### Task 3: `timings_ms` on explain

**Files:** `schemas/memory.py`, `hybrid_search.py`, `routers/memories.py`, `test_memories_api.py`, `test_hybrid_search.py`

- `explain=true` → `timings_ms` with five keys. Disabled store → `0`.
- `explain=false` → `timings_ms` null/absent.
- `logger.info` with the timings dict on every search.

---

### Task 4: Benchmarks + docs

**Files:** `tests/test_hybrid_benchmarks.py`, `spec/v2_extension_plan.md`, `spec/03-architecture.md`, `test_postgres_api.py` (assert timings when explain on one existing graph/KV search if cheap)

Tick Phase 3 checkboxes. Update hybrid architecture section.
