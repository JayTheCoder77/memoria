# Memoria v2 Phase 2 — Graph Store

**Status:** Ready for implementation  
**Parent:** `spec/v2_extension_plan.md`  
**Depends on:** `spec/v2-phase0-foundations.md`, `spec/v2-phase1-kv-store.md`  
**Date:** 2026-09-04

Phase 2 adds Postgres `graph_nodes` / `graph_edges` so relationship queries can surface linked memories. Canonical rows stay in `memories`. KV stays as in Phase 1. Soft-invalidation keeps history.

## Goal

With `MEMORIA_ENABLE_GRAPH` on (the new default), remember can write graph triples, `add_edge` invalidates prior valid edges with the same `(org, subject, relation)`, and search unions 1–2 hop linked memories with vector and KV hits. `relevance = max(vector_similarity, kv_match, graph_score)`.

## Non-goals

- No Neo4j / Memgraph
- No dashboard views for nodes/edges
- No MCP schema change for `graph_triples` / `as_of` (HTTP first)
- No `entities` / `embedding_model` / `embedding_version` columns on `memories`
- No Phase 3 parallel orchestrator service — keep wiring in persist + search router
- No relation allow-list table (open string set)
- PATCH does not rewrite graph

## Decisions (locked)

| Topic | Choice |
|-------|--------|
| Scope | Full Phase 2: tables, Postgres `GraphStore`, soft-invalidate, write fan-out, 1–2 hop search union, `explain` `graph_hops`, `as_of` query param |
| Ingest | Explicit `graph_triples` when present; otherwise conservative heuristic on `content` |
| Search mix | Union by `memory_id`; graph-only hits allowed (`vector_similarity = 0`) |
| Flag | `enable_graph` defaults **true**; KV stays on |
| Query seeds | **LLM first** when the org has an OpenRouter key; **rules fallback** otherwise or on LLM/decrypt failure |
| Remember vs graph errors | Memory persist is source of truth. Graph failures are **logged and ignored** |
| Hop score | 1 hop → `graph_score = 1.0`; 2 hops → `0.5`; min hops wins if both |
| `as_of` | Optional `GET /memories/search?as_of=` ISO datetime; default current valid edges |

## Architecture

```
POST /memories  or  worker persist_candidate
  → insert or dedup bump on memories
  → persist_kv_facts (unchanged)
  → if enable_graph: resolve triples → upsert_node ×2 + add_edge (savepoint; log+continue)
  → return MemoryOut

GET /memories/search
  → vector + KV union (Phase 1)
  → derive_graph_seeds(q): LLM if org key else rules
  → graph.memories_for_subgraph(org, seeds, hops=2) with hop distances
  → load missing memories (org + session scope)
  → relevance = max(vector, kv_match or 0, graph_score or 0)
  → explain: graph_hops + "graph" in sources when graph contributed
```

| Unit | Responsibility |
|------|----------------|
| `GraphNode` / `GraphEdgeRow` ORM | Map tables |
| `PostgresGraphStore` / `InMemoryGraphStore` | Protocol methods; org isolation |
| `normalize_graph_token` | strip + lowercase for keys and relations |
| `resolve_graph_triples` | Explicit then heuristic; cap |
| `persist_graph_facts` | Fan-out; never fails remember |
| `derive_graph_seeds` | Query → entity keys |

Reuse `normalize_kv_token` **or** a sibling `normalize_graph_token` with the same strip+lowercase behavior (do not change KV).

## Data model

Alembic revision `0006_graph`, revises `0005_kv_facts`.

```sql
CREATE TABLE graph_nodes (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id      uuid NOT NULL REFERENCES orgs(id),
  entity_key  text NOT NULL,
  label       text NOT NULL,
  properties  jsonb NOT NULL DEFAULT '{}',
  created_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, entity_key)
);

CREATE TABLE graph_edges (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id      uuid NOT NULL REFERENCES orgs(id),
  subject_id  uuid NOT NULL REFERENCES graph_nodes(id),
  relation    text NOT NULL,
  object_id   uuid NOT NULL REFERENCES graph_nodes(id),
  memory_id   uuid REFERENCES memories(id) ON DELETE SET NULL,
  valid       boolean NOT NULL DEFAULT true,
  valid_from  timestamptz NOT NULL DEFAULT now(),
  valid_to    timestamptz,
  confidence  float NOT NULL DEFAULT 1.0,
  properties  jsonb NOT NULL DEFAULT '{}',
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_graph_nodes_org_key ON graph_nodes (org_id, entity_key);
CREATE INDEX idx_graph_edges_org     ON graph_edges (org_id);
CREATE INDEX idx_graph_edges_subject ON graph_edges (subject_id) WHERE valid = true;
CREATE INDEX idx_graph_edges_object  ON graph_edges (object_id)  WHERE valid = true;
CREATE INDEX idx_graph_edges_memory  ON graph_edges (memory_id);
CREATE INDEX idx_graph_edges_valid_time ON graph_edges (org_id, valid_from, valid_to);
```

SQLAlchemy: `GraphNode`, `GraphEdgeRow` (`GraphEdge` is already the dataclass in `stores.types`).

## Config

| Setting | Type | Default |
|---------|------|---------|
| `enable_graph` | bool | `true` |
| `graph_max_edges_per_add` | int | `8` |

`enable_kv` stays `true`. Update `.env.example`: `MEMORIA_ENABLE_GRAPH=true`, `MEMORIA_GRAPH_MAX_EDGES_PER_ADD=8`.

## Store behavior

`upsert_node`: normalize `entity_key`; skip empty (return a random UUID without writing, matching “skip empty tokens”). Default `label` `"entity"` if empty after strip. Unique `(org_id, entity_key)`: on conflict keep existing id; do not overwrite label/properties in Phase 2 (YAGNI).

`add_edge`:
1. Normalize subject, relation, object. Skip if any empty (return random UUID, no write).
2. `upsert_node` both ends with label `"entity"`.
3. Find currently **valid** edges for `(org_id, subject_id, relation)` (any object). Set `valid=false`, `valid_to=now()` on each.
4. Insert new edge `valid=true`, `valid_from=now()`, `valid_to=NULL`, given `memory_id` and `confidence`.
5. If `memory_id` is set, it must belong to `org_id` or skip the write (same ownership rule as KV).

Never DELETE edges.

`neighbors`: BFS from `entity_key` up to `hops` (clamp 1–2). Return `GraphEdge` dataclasses with **keys** not UUIDs. Org-scoped.

Validity:
- `as_of is None` and `valid_only=True` (default): `valid = true`.
- `as_of` set: include edge if `valid_from <= as_of` and (`valid_to` is NULL or `valid_to > as_of`). Ignore the `valid` boolean when `as_of` is set.

`memories_for_subgraph`: unique non-null `memory_id`s on edges in the expanded neighborhood (hops, default `valid_only` / current time). Also expose hop distance for search: implement `memories_for_subgraph` as today **and** a helper `memory_hops(org_id, entity_keys, *, hops=2, as_of=None) -> dict[UUID, int]` mapping memory_id → min hops (1 or 2). Search uses the helper. If adding a protocol method is too invasive, keep the helper as a store method not on the Protocol (InMemory + Postgres both have `memory_hops`).

## Write path

`graph_triples` on `Candidate` and `MemoryCreate`: `list[dict]` with `subject`, `relation`, `object` (optional `confidence` float, default 1.0).

LLM extractor JSON adds optional `"graph_triples":[{"subject","relation","object"}]`. Missing is valid.

`resolve_graph_triples`:
1. Explicit non-empty after normalize → use, truncated to `graph_max_edges_per_add`.
2. Else heuristic on `content` only, same cap.
3. Heuristic (conservative; `"explain skeleton probe"` emits **zero**):
   - `lives in X` / `moved to X` → `(user, lives_in, x)`
   - `prefer X` / `prefers X` → `(user, prefers, x)`
   - `works on X` → `(user, works_on, x)`
4. Subject for heuristics is always the token `user` (org-scoped graph, no per-user nodes in Phase 2).

`persist_graph_facts`: same savepoint / log / continue pattern as `persist_kv_facts`. Dedup bump still writes edges against existing `memory_id`. `enable_graph=false` → no-op.

## Read path

When `enable_graph` is false: Phase 1 search; `graph_hops` stays JSON null.

When true, after KV union:
1. `seeds = derive_graph_seeds(q)` — cap 12, normalized, deduped.
2. `hops_map = graph.memory_hops(org, seeds, hops=2, as_of=as_of)`.
3. For each memory_id, org-scoped `repo.get`; session filter like KV.
4. Merge into union. Graph-only: `vector_similarity=0`, `kv_match` unchanged (null), `graph_hops` set, `graph_score = 1.0 if hops==1 else 0.5`.
5. `relevance = max(similarity, kv_match or 0, graph_score or 0)`.

`derive_graph_seeds`:
- LLM: `{"entities":[string,...]}` temperature 0 json_object. Empty valid. Errors → rules.
- Rules: tokens length ≥ 3; plus `lives in X`, `prefer X`, `works on X`. Do not fail search.

Search graph errors: log, skip graph contribution.

`as_of`: FastAPI `Query` optional datetime. Invalid parse → 422 (FastAPI default). Passed only into graph hop lookup, not vector.

## Explain

Graph contributed (`graph_hops` is 1 or 2):

- `sources` includes `"graph"`
- `graph_hops` is that int
- `kv_match` still null unless KV also hit

Graph-only: `sources: ["graph"]`, `vector_similarity: 0.0`.

Vector-only: `graph_hops: null` (Phase 1 shape).

## Error handling

| Failure | Behaviour |
|---------|-----------|
| Graph write | Savepoint, log, remember 201 |
| Graph search | Log, omit graph hits |
| LLM seed derivation | Log, rules fallback |
| Decrypt OpenRouter | Already handled; rules for both KV and graph seeds |
| `enable_graph=false` | `NoOpGraphStore` |

## Testing

- Store: upsert node idempotent; add_edge invalidates old `lives_in`; `neighbors(as_of=old)` still returns invalidated edge; other org isolated; empty keys skipped; foreign `memory_id` skipped.
- Persist: explicit triples; heuristic `lives in`; probe writes none; cap 8; put/add_edge raise still 201.
- Search: graph-only admission outside vector over-fetch; session scope; `explain` `graph_hops`; `enable_graph=false` null hops; 2-hop score 0.5.
- `derive_graph_seeds` LLM mock + fallback.
- Full in-memory suite with flags on.

## Docs

Tick Phase 2 boxes in `spec/v2_extension_plan.md`. Update `spec/03-architecture.md` hybrid section.

## Exit criteria

- City change invalidates old `lives_in` but history is queryable via `as_of`.
- Relationship-linked memories appear in search when vector is weak.
- Remember never fails solely because graph failed.
- KV path unchanged when graph is off.
