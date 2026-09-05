# Memoria v2 Phase 3 — Unified Fusion Retrieval

**Status:** Ready for implementation  
**Parent:** `spec/v2_extension_plan.md`  
**Depends on:** Phase 0–2 specs  
**Date:** 2026-09-05

Phase 3 extracts hybrid search into a `HybridRetriever` that fans Vector, KV, and Graph reads out concurrently. Ranking stays exactly as Phase 1–2. `explain=true` gains request-level per-store latency.

## Goal

`GET /memories/search` (MCP `recall`) remains the single fused endpoint. The three store reads overlap in time. `explain=true` returns existing per-hit `score_details` plus `timings_ms`. A small in-memory benchmark suite covers fact-lookup, relationship, semantic, and temporal queries.

## Non-goals

- No MCP schema change for `explain` / `timings_ms` / `as_of` (HTTP first)
- No parallel remember / worker writes
- No last-read recency, learned importance, or learned fusion weights
- No combining KV and graph into one LLM call (Phase 4)
- No asyncio / async SQLAlchemy conversion
- No CI assertion of p95 &lt; 200 ms (flaky)

## Decisions (locked)

| Topic | Choice |
|-------|--------|
| Ranking | Unchanged: `relevance = max(vector, kv_match, graph_score)`; KV exact `1.0`; 1-hop `1.0`; 2-hop `0.5`; then existing `retrieval_score` weights |
| Parallelism | `concurrent.futures.ThreadPoolExecutor` (`max_workers=3`); FastAPI `search` stays sync |
| SQLAlchemy | Request `Session` is not shared across threads. Isolated sessions only when live Postgres stores are in use (`PostgresKVStore` / `PostgresGraphStore` / `PostgresVectorStore` wrapping `PostgresMemoryRepository`). In-memory tests share injected stores |
| Embed | Retriever owns embed so `timings_ms.embed` is accurate |
| Vector API | Router uses `VectorStore.search` (`PostgresVectorStore` adapter), not `repo.search` directly |
| Missing rows | After futures return, `repo.get` on the **request** session for KV/graph-only memory ids; session-scope filter unchanged |
| Failures | Per-store: log and contribute empty results (same as Phase 1–2) |
| Latency | Request-level `timings_ms` when `explain=true`: `embed`, `vector`, `kv`, `graph`, `total` (milliseconds, float). Disabled stores: `0`. Always log the dict even when `explain` is false |
| Workers env | No new flag; hard-code `max_workers=3` |

## Architecture

```
GET /memories/search
  → HybridRetriever.search
       embed(q)
       parallel:
         VectorStore.search(embedding)
         derive_kv_candidates(q) → kv.search_keys
         derive_graph_seeds(q) → graph.memory_hops(..., hops=2, as_of)
       union by memory_id
       repo.get missing ids (org + session scope)
       score + token-budget truncation
  → MemorySearchResponse (score_details and timings_ms if explain)
```

| Unit | Responsibility |
|------|----------------|
| `HybridRetriever` | Orchestrate embed, parallel reads, union, score, truncate, timings |
| `SearchTimings` | `embed` / `vector` / `kv` / `graph` / `total` milliseconds |
| `get_vector_store` | `PostgresVectorStore(repo)` |
| GraphStore protocol | Add `memory_hops` (already on concrete stores) |

## HTTP

`MemorySearchResponse`:

```json
{
  "memories": [ "MemoryOut..." ],
  "timings_ms": {
    "embed": 1.2,
    "vector": 12.0,
    "kv": 40.0,
    "graph": 38.0,
    "total": 45.0
  }
}
```

`timings_ms` is omitted/`null` when `explain` is false. Per-hit `score_details` is unchanged.

## Tests

- Retriever ranking matches current fusion (vector ∪ KV ∪ graph, session scope, flags off).
- Overlap: instrumented stores; all three intervals overlap.
- One store raising does not fail search; other stores still contribute.
- `explain=true` includes `timings_ms` keys; `explain=false` omits it.
- Benchmarks: fact-lookup, relationship, semantic, temporal (`as_of`) — assert ranking/explain, not wall-clock budgets.
