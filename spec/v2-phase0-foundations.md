# Memoria v2 Phase 0 — Foundations

**Status:** Ready for implementation  
**Parent:** `spec/v2_extension_plan.md`  
**Date:** 2026-09-04

Phase 0 makes hybrid memory *pluggable* without changing default retrieval. KV and Graph stay off. Existing tests must pass with flags at defaults.

## Goal

Vector-only search behaviour is unchanged. Interfaces, feature flags, fusion-weight config, and an opt-in `explain` skeleton exist so Phase 1–3 can fill in stores instead of rewriting search.

## Non-goals

- No `kv_facts` / `graph_nodes` / `graph_edges` tables or Alembic migrations
- No extraction schema changes (`kv_triples` / `graph_triples`)
- No parallel fusion orchestrator
- No MCP `explain` / `as_of` parameters (HTTP first)
- No `entities` / `embedding_model` / `embedding_version` columns

## Architecture

`MemoryRepository` remains the canonical CRUD + cosine search API used by write, dedup, list, patch, and delete.

New store protocols sit beside it. They are **not** a second source of truth.

| Unit | Responsibility | Depends on |
|------|----------------|------------|
| `VectorStore` | Embedding upsert + similarity search scoped by `org_id` / optional `session_id` | Canonical memory row already exists |
| `KVStore` | Exact fact put/get/search | Phase 1; Phase 0 is a no-op |
| `GraphStore` | Node/edge upsert, neighbors, memory linking | Phase 2; Phase 0 is a no-op |
| `PostgresVectorStore` | Adapter: delegates `search`/`similar` to `MemoryRepository`. `upsert` is a no-op because the embedding is already on `memories` | `MemoryRepository` |
| `NoOpKVStore` / `NoOpGraphStore` | Empty results; no I/O | Settings flags |

Search in Phase 0 still runs in `routers/memories.py`: embed → `repo.search` → `retrieval_score` → token budget. `PostgresVectorStore` is constructed and available for later wiring; it must be covered by unit tests that call the protocol methods.

When `explain=true`, the router attaches `score_details` after scoring. It does not query KV or Graph.

```
GET /memories/search?q=...&explain=true
  → embed(q)
  → MemoryRepository.search (org scoped)
  → retrieval_score (configurable weights + half-life)
  → optional score_details skeleton
  → truncate_to_token_budget
```

## Config

`memory_api.config.Settings` (env prefix `MEMORIA_`):

| Setting | Type | Default |
|---------|------|---------|
| `enable_kv` | bool | `false` |
| `enable_graph` | bool | `false` |
| `fusion_weight_relevance` | float | `0.6` |
| `fusion_weight_importance` | float | `0.2` |
| `fusion_weight_recency` | float | `0.2` |
| `recency_halflife_days` | float | `14.0` |

Three separate floats, not a JSON object — matches the rest of Settings.

`scoring.retrieval_score` and `recency_weight` must read these values (passed in or via settings), not only module constants. Keep the current constants as the defaults so existing tests that call `retrieval_score(...)` without extra kwargs still pass.

If `enable_kv` or `enable_graph` is true in Phase 0, still use the no-op stores. Real implementations arrive in later phases. Flags exist so tests can assert they default off and so later code can branch.

Document the new keys in `apps/memory-api/.env.example`.

## Protocols

Live in `apps/memory-api/src/memory_api/stores/`.

```python
class VectorStore(Protocol):
    def upsert(self, memory_id: UUID, embedding: list[float], metadata: dict) -> None: ...
    def search(
        self,
        org_id: UUID,
        query_embedding: list[float],
        *,
        session_id: str | None,
        limit: int,
    ) -> list[ScoredMemory]: ...

class KVStore(Protocol):
    def put(
        self,
        org_id: UUID,
        memory_id: UUID,
        fact_type: str,
        entity: str,
        *,
        value: str | None,
        importance: float,
        user_key: str | None = None,
    ) -> None: ...
    def get(self, org_id: UUID, fact_type: str, entity: str) -> KVFact | None: ...
    def search_keys(self, org_id: UUID, candidates: list[tuple[str, str]]) -> list[KVFact]: ...
    def by_org(self, org_id: UUID, *, user_key: str | None = None) -> list[KVFact]: ...

class GraphStore(Protocol):
    def upsert_node(
        self, org_id: UUID, entity_key: str, label: str, properties: dict | None = None
    ) -> UUID: ...
    def add_edge(
        self,
        org_id: UUID,
        subject_key: str,
        relation: str,
        object_key: str,
        *,
        memory_id: UUID | None,
        confidence: float = 1.0,
    ) -> UUID: ...
    def neighbors(
        self,
        org_id: UUID,
        entity_key: str,
        *,
        hops: int = 1,
        valid_only: bool = True,
        as_of: datetime | None = None,
    ) -> list[GraphEdge]: ...
    def memories_for_subgraph(
        self, org_id: UUID, entity_keys: list[str], *, hops: int = 1
    ) -> list[UUID]: ...
```

Supporting types (`ScoredMemory`, `KVFact`, `GraphEdge`) are dataclasses in the same package.

```python
@dataclass(frozen=True)
class ScoredMemory:
    memory: Memory
    similarity: float
```

`PostgresVectorStore.search` maps each repository `(Memory, float)` into `ScoredMemory`. Access-count touch stays inside `MemoryRepository.search`; the adapter does not double-touch.

`NoOpKVStore.get` / `search_keys` / `by_org` return `None` / `[]`. `put` is a no-op. `NoOpGraphStore.upsert_node` / `add_edge` return a random UUID; `neighbors` / `memories_for_subgraph` return `[]`.

## HTTP: explain skeleton

`GET /memories/search` gains `explain: bool = False`.

`MemoryOut.score_details` is optional. Omitted (`null`) when `explain` is false.

When `explain` is true, every returned memory includes:

```json
{
  "relevance": 0.88,
  "importance": 0.70,
  "recency": 0.55,
  "sources": ["vector"],
  "vector_similarity": 0.88,
  "kv_match": null,
  "graph_hops": null,
  "weights": {
    "relevance": 0.6,
    "importance": 0.2,
    "recency": 0.2
  }
}
```

Field rules for Phase 0:

- `vector_similarity` is the cosine similarity from the repository (the value already fed into `retrieval_score`)
- `relevance` equals `vector_similarity` (max of one source)
- `importance` is `memory.importance`
- `recency` is `recency_weight(memory.created_at)` using configured half-life
- `sources` is always `["vector"]`
- `kv_match` and `graph_hops` are always JSON `null`
- `score` on `MemoryOut` remains the fused `retrieval_score` (unchanged ranking)

Do not add `as_of` in Phase 0.

## Error handling

- Invalid `explain` query values follow FastAPI bool parsing (same as other bool query params if any exist; otherwise default FastAPI)
- Fusion weights are not validated beyond type in Phase 0 (no “must sum to 1” check)
- Store no-ops never raise

## Testing

- Existing search/retrieval tests stay green with no new query params
- New: default settings have KV/Graph disabled
- New: `PostgresVectorStore` (or adapter over `InMemoryMemoryRepository`) `search` matches repository ranking
- New: `NoOpKVStore` / `NoOpGraphStore` return empty
- New: `GET /memories/search?explain=true` includes full `score_details` keys; without `explain`, `score_details` is null/absent
- New: `retrieval_score` / `recency_weight` honor passed-in weights / half-life

Run: `cd apps/memory-api && uv run pytest` and `uv run ruff check src tests`.

## Docs

- Tick Phase 0 boxes in `spec/v2_extension_plan.md` that this work completes
- Add a short “hybrid stores (Phase 0)” note in `spec/03-architecture.md`: protocols exist; only vector is live
- `.env.example` lists the new `MEMORIA_*` keys

## Exit criteria

1. Flags off by default; vector path ranking identical to today
2. Protocols + no-op KV/Graph + vector adapter exist and are tested
3. `explain=true` returns the full `score_details` key set with null KV/Graph fields
4. Fusion weights and recency half-life are configurable via settings
