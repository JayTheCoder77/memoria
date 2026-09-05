# Memoria v2 Extension Plan

**Hybrid Memory: Vector + KV + Graph**

> Status: Draft for implementation  
> Based on: Mem0 hybrid pattern (Vector + KV + Graph) as described in *AI Engineering from Scratch* — Phase 14, Lesson 09  
> Current baseline: Memoria (Postgres + pgvector, FastAPI Memory API, MCP adapter, multi-tenant org/session model)  
> Target: Production-grade hybrid memory with parallel stores, fusion scoring, soft temporal invalidation, and multi-class query support

---

## 1. Executive Summary

Memoria currently stores memories in **Postgres + pgvector** and ranks them with a weighted combination of semantic similarity, importance, and recency.

This is insufficient for three distinct query classes that production agents issue in the same session:

| Query class              | Example                                          | Best store   |
|--------------------------|--------------------------------------------------|--------------|
| Semantic similarity      | “what did we discuss about agent drift last week?” | Vector      |
| Exact fact lookup        | “what is the user’s preferred language?”         | KV           |
| Relationship reasoning   | “which projects share the same billing entity?”  | Graph        |

**v2 goal:** Write every durable fact to three stores in parallel and fuse results on retrieval using a weighted score of relevance, importance, and recency.

```
score = w_relevance  × relevance(q, record)
      + w_importance × importance(record)
      + w_recency    × recency(record)
```

Postgres remains the single source of truth for the canonical memory row. Vector, KV, and Graph act as specialized indexes linked by `memory_id`.

---

## 2. Design Principles

1. **Canonical row first** — Every memory lives in `memories`. Secondary stores reference it; they are never independent sources of truth.
2. **Parallel write, fused read** — `add` / extraction fans out to all three stores. `search` queries them in parallel and fuses.
3. **Soft invalidation on graph** — Contradictions mark old edges `valid = false` (with `valid_to`); they are never hard-deleted so temporal queries remain possible.
4. **Scope enforcement at query layer** — `org_id` is mandatory on every read/write. `session_id` and optional agent scope are honored when supplied.
5. **Feature-flagged rollout** — KV and Graph can be disabled independently. Existing vector-only path must continue to work.
6. **Explainability** — `explain=true` returns per-store scores and the final fused score.
7. **Operational guardrails** — Cap edges and KV triples per write; control `fact_type` vocabulary; plan for embedding drift.

---

## 3. Target Architecture

```
                    ┌─────────────────────────────────────┐
                    │           Memory API (FastAPI)       │
                    │  add() / search() / update() / emit  │
                    └──────────────┬──────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
       ┌─────────────┐     ┌─────────────┐      ┌─────────────┐
       │ Vector Store│     │  KV Store   │      │ Graph Store │
       │ (pgvector)  │     │ (Postgres)  │      │ (Postgres)  │
       └─────────────┘     └─────────────┘      └─────────────┘
              │                    │                    │
              └────────────────────┼────────────────────┘
                                   ▼
                          Fusion Scorer
                 (relevance + importance + recency)
```

### Scope taxonomy (aligned with Mem0)

| Scope     | Keying                         | Lifetime              | Use case                          |
|-----------|--------------------------------|-----------------------|-----------------------------------|
| User/Org  | `org_id` (+ optional user key) | Cross-session         | Preferences, profile, decisions   |
| Session   | `org_id` + `session_id`        | Single thread         | Ephemeral working context         |
| Agent     | `org_id` + agent identifier    | Per-agent instance    | Agent-specific state (future)     |

---

## 4. Data Model Changes

### 4.1 Canonical memory (existing, minor extensions)

Keep the current `memories` table. Recommended additions:

```sql
-- Optional columns / metadata enrichment
ALTER TABLE memories
  ADD COLUMN IF NOT EXISTS entities text[],           -- denormalized entity list for fast boost
  ADD COLUMN IF NOT EXISTS fact_types text[],         -- denormalized KV fact types
  ADD COLUMN IF NOT EXISTS embedding_model text,      -- track model for drift / re-embed
  ADD COLUMN IF NOT EXISTS embedding_version int;     -- re-embed counter
```

### 4.2 KV Store

```sql
CREATE TABLE kv_facts (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        uuid NOT NULL REFERENCES orgs(id),
  memory_id     uuid NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
  user_key      text,                          -- optional finer-grained key (user/agent)
  fact_type     text NOT NULL,                 -- controlled vocabulary: city, preference, project, decision, ...
  entity        text NOT NULL,                 -- normalized entity / value key
  value         text,                          -- optional richer payload
  importance    float NOT NULL DEFAULT 0.5,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),

  -- Soft uniqueness: latest wins; history can be kept via memory_id provenance
  UNIQUE (org_id, fact_type, entity)
);

CREATE INDEX idx_kv_facts_org_type ON kv_facts (org_id, fact_type);
CREATE INDEX idx_kv_facts_memory   ON kv_facts (memory_id);
CREATE INDEX idx_kv_facts_org_user ON kv_facts (org_id, user_key) WHERE user_key IS NOT NULL;
```

**Key shape:** `(org_id, fact_type, entity)` — mirrors the lesson’s `(user_id, fact_type, entity)`.

### 4.3 Graph Store

```sql
CREATE TABLE graph_nodes (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id      uuid NOT NULL REFERENCES orgs(id),
  entity_key  text NOT NULL,                   -- stable normalized entity identifier
  label       text NOT NULL,                   -- person | project | city | org | concept | ...
  properties  jsonb NOT NULL DEFAULT '{}',
  created_at  timestamptz NOT NULL DEFAULT now(),

  UNIQUE (org_id, entity_key)
);

CREATE TABLE graph_edges (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id      uuid NOT NULL REFERENCES orgs(id),
  subject_id  uuid NOT NULL REFERENCES graph_nodes(id),
  relation    text NOT NULL,                   -- lives_in | owns_project | prefers | depends_on | ...
  object_id   uuid NOT NULL REFERENCES graph_nodes(id),
  memory_id   uuid REFERENCES memories(id) ON DELETE SET NULL,  -- provenance
  valid       boolean NOT NULL DEFAULT true,
  valid_from  timestamptz NOT NULL DEFAULT now(),
  valid_to    timestamptz,                     -- NULL = currently valid
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

**Conflict rule (Mem0g-style):**  
When inserting a new edge with the same `(subject, relation)` that already has a valid edge, set `valid = false` and `valid_to = now()` on the old edge, then insert the new edge as valid. Never delete.

---

## 5. Storage Interfaces

Introduce clean abstractions so implementations can evolve (e.g. later swap graph to Neo4j/Memgraph).

```python
# Conceptual interfaces (Python)

class VectorStore(Protocol):
    def upsert(self, memory_id: UUID, embedding: list[float], metadata: dict) -> None: ...
    def search(self, org_id: UUID, query_embedding: list[float], *, session_id: str | None, limit: int) -> list[ScoredMemory]: ...

class KVStore(Protocol):
    def put(self, org_id: UUID, memory_id: UUID, fact_type: str, entity: str, *, value: str | None, importance: float, user_key: str | None = None) -> None: ...
    def get(self, org_id: UUID, fact_type: str, entity: str) -> KVFact | None: ...
    def search_keys(self, org_id: UUID, candidates: list[tuple[str, str]]) -> list[KVFact]: ...
    def by_org(self, org_id: UUID, *, user_key: str | None = None) -> list[KVFact]: ...

class GraphStore(Protocol):
    def upsert_node(self, org_id: UUID, entity_key: str, label: str, properties: dict | None = None) -> UUID: ...
    def add_edge(self, org_id: UUID, subject_key: str, relation: str, object_key: str, *, memory_id: UUID | None, confidence: float = 1.0) -> UUID: ...
    def neighbors(self, org_id: UUID, entity_key: str, *, hops: int = 1, valid_only: bool = True, as_of: datetime | None = None) -> list[Edge]: ...
    def memories_for_subgraph(self, org_id: UUID, entity_keys: list[str], *, hops: int = 1) -> list[UUID]: ...
```

Feature flags:

```
MEMORIA_ENABLE_KV=true
MEMORIA_ENABLE_GRAPH=true
MEMORIA_FUSION_WEIGHTS={"relevance": 0.6, "importance": 0.2, "recency": 0.2}
MEMORIA_GRAPH_MAX_EDGES_PER_ADD=8
MEMORIA_KV_MAX_TRIPLES_PER_ADD=6
MEMORIA_RECENCY_HALFLIFE_DAYS=14
```

---

## 6. Write Path

### 6.1 Explicit `remember` / `POST /memories`

1. Validate auth + org scope.
2. Run extraction (or accept pre-structured payload) → obtain:
   - `content`
   - `memory_type`
   - `importance`
   - `kv_triples: list[tuple[fact_type, entity]]`
   - `graph_triples: list[tuple[subject, relation, object]]`
   - `entities: list[str]`
3. Embed `content`.
4. Dedup against existing memories (cosine ≥ threshold → bump importance / access_count, skip insert).
5. Insert canonical row into `memories`.
6. **Parallel fan-out:**
   - Vector: store embedding (already part of insert or separate upsert).
   - KV: upsert each triple (respect cap).
   - Graph: upsert nodes + add edges with soft-invalidation (respect cap + confidence).
7. Return memory id + summary of secondary writes.

### 6.2 Async extraction worker (`emit` → `event_buffer`)

Same fan-out after the extractor produces candidates.  
Heuristic extractor remains the offline / no-key fallback; LLM extractor becomes primary when an org key is present.

### 6.3 Recommended extractor output shape

```json
{
  "content": "User prefers TypeScript over JavaScript for new services",
  "memory_type": "semantic",
  "importance": 0.75,
  "kv_triples": [
    ["preference", "typescript"],
    ["language", "typescript"]
  ],
  "graph_triples": [
    ["user", "prefers", "typescript"],
    ["user", "avoids", "javascript"]
  ],
  "entities": ["typescript", "javascript"]
}
```

Prefer **ADD-only** extraction. Let graph soft-invalidation and KV upsert handle evolution of facts.

---

## 7. Read Path (Fusion Retrieval)

### 7.1 Pipeline

```
1. Auth + scope filters (org_id required; session_id optional)
2. Embed query (in-process)
3. Extract entities + candidate KV keys from query
   (lightweight rules first; optional small LLM assist later)
4. Parallel retrieval:
   a. Vector  → top-N by cosine (org/session filtered)
   b. KV      → exact / near key matches
   c. Graph   → 1–2 hop neighborhood → linked memory_ids
5. Union candidates by memory_id
6. Score each candidate:
   relevance  = max(
                  vector_similarity,
                  kv_match_score,      # 0.9–1.0 for exact
                  graph_path_score     # decays with hops / confidence
                )
   importance = memory.importance
   recency    = 0.5 ** (age_days / half_life_days)
7. final = w_r * relevance + w_i * importance + w_c * recency
8. Optional token-budget truncation
9. Return top-k (+ explain breakdown when requested)
```

### 7.2 Default fusion weights

```
w_relevance  = 0.6
w_importance = 0.2
w_recency    = 0.2
```

Make these configurable per deployment / org so different products can bias:

- Chat / coding agents → higher recency
- Compliance / policy agents → higher importance
- Pure retrieval agents → higher relevance

### 7.3 Temporal queries

Support an optional `as_of` (or `valid_at`) parameter:

- Graph: only traverse edges where `valid_from <= as_of` and (`valid_to IS NULL` or `valid_to > as_of`)
- Vector / KV: still return current facts unless future temporal columns are added to the canonical row

This enables “where did the user live in March?” style questions.

### 7.4 Explain mode

```json
{
  "id": "...",
  "content": "...",
  "score": 0.81,
  "score_details": {
    "relevance": 0.92,
    "importance": 0.70,
    "recency": 0.55,
    "sources": ["vector", "kv", "graph"],
    "vector_similarity": 0.88,
    "kv_match": 1.0,
    "graph_hops": 1
  }
}
```

---

## 8. Phased Implementation Plan

### Phase 0 — Foundations (3–5 days)

**Objective:** Pluggable stores without breaking current behaviour.

- [x] Define `VectorStore`, `KVStore`, `GraphStore` protocols / abstract classes
- [x] Wrap existing pgvector logic behind `VectorStore`
- [x] Add feature flags and config for fusion weights
- [x] Add `explain` support skeleton on search responses
- [x] Document hybrid mental model in `spec/`
- [x] Ensure all existing tests still pass with flags off

**Exit criteria:** Vector-only path unchanged; interfaces ready for KV/Graph implementations.

---

### Phase 1 — KV Store (1 week)

**Objective:** Fast exact fact lookup.

- [x] Alembic migration for `kv_facts`
- [x] `KVStore` Postgres implementation
- [x] Extraction changes to emit `kv_triples`
- [x] Write path: fan-out to KV on successful insert (with cap)
- [x] Read path: candidate key derivation + KV lookup in parallel with vector
- [x] Fusion: incorporate KV match score into relevance
- [x] Tests: exact preference / city / decision lookups
- [x] Guardrail: open fact_type set in Phase 1 (hard allow-list deferred)

**Exit criteria:** Fact-lookup queries return correct results via KV even when pure vector ranking is weak.

---

### Phase 2 — Graph Store + Soft Invalidation (1.5–2 weeks)

**Objective:** Relationship reasoning and temporal history.

- [x] Alembic migration for `graph_nodes` + `graph_edges`
- [x] `GraphStore` Postgres implementation
- [x] Soft-invalidation logic on `(subject, relation)` conflict
- [x] Extraction changes to emit `graph_triples`
- [x] Write path: node upsert + edge insert with invalidation (with caps + confidence)
- [x] Read path: entity extraction → 1–2 hop expansion → linked memories
- [x] Graph-derived relevance score in fusion
- [x] Basic `as_of` support on graph traversal
- [x] Tests:
  - [x] City change invalidates old `lives_in` edge but keeps history
  - [x] Multi-hop “what projects does X own?” style queries
  - [x] Scope isolation (no cross-org edges)

**Exit criteria:** Relationship queries work; contradictions soft-invalidate; temporal history preserved.

---

### Phase 3 — Unified Fusion Retrieval (1 week)

**Objective:** Single coherent hybrid `search`.

- [x] Parallel orchestrator that fans out to Vector + KV + Graph
- [x] Candidate union + multi-signal scoring
- [x] Configurable fusion weights
- [x] Token-budget truncation (reuse existing helper)
- [x] Full `explain=true` response shape
- [x] Latency instrumentation per store
- [x] Benchmark suite covering the three query classes + temporal

**Exit criteria:** One `recall` / search endpoint returns fused results; explain mode is usable for debugging.

---

### Phase 4 — Extraction Alignment (1–1.5 weeks)

**Objective:** One extraction pass feeds all three stores cleanly.

- [ ] Update LLM extractor prompt/schema to return kv + graph triples + entities
- [ ] Keep heuristic extractor as fallback (regex / keyword rules for preferences, decisions, fixes)
- [ ] Make LLM extractor default when org has a key
- [ ] ADD-only policy with graph soft-invalidation + KV upsert handling updates
- [ ] Improve dedup with optional entity overlap signal
- [ ] Cap enforcement and low-confidence triple dropping
- [ ] Tests for end-to-end write → three-store population

**Exit criteria:** Successful extraction populates Vector + KV + Graph from a single pass.

---

### Phase 5 — Hardening & Operations (1 week)

**Objective:** Production readiness and long-term quality.

| Risk                | Mitigation                                                                 |
|---------------------|----------------------------------------------------------------------------|
| Embedding drift     | Job to re-embed top-N most-accessed memories; track `embedding_version`    |
| KV schema creep     | Controlled `fact_type` vocabulary + periodic audit endpoint / script       |
| Graph explosion     | Hard caps per `add`; confidence threshold; monitoring on edge count        |
| Scope leakage       | Continue enforcing `org_id` at repository layer (already in design)        |
| Latency regression  | Parallel queries; keep in-process embeddings; HNSW; measure p95 per store  |

Additional work:

- [ ] Temporal query polish (`as_of`)
- [ ] Dashboard read-only views for KV keys and graph edges
- [ ] Consolidation job awareness of KV/Graph (avoid orphaned secondary rows)
- [ ] Documentation: hybrid architecture, weight tuning guide, failure modes
- [ ] Load / quality benchmarks (semantic, fact-lookup, relationship, temporal)

**Exit criteria:** Guardrails live; observability in place; docs updated; no regressions on core MCP tools.

---

## 9. Timeline (Aggressive but Realistic)

| Phase | Focus                              | Duration     |
|-------|------------------------------------|--------------|
| 0     | Interfaces + flags                 | 3–5 days     |
| 1     | KV store                           | 1 week       |
| 2     | Graph store + soft invalidation    | 1.5–2 weeks  |
| 3     | Fusion retrieval                   | 1 week       |
| 4     | Extraction alignment               | 1–1.5 weeks  |
| 5     | Hardening & ops                    | 1 week       |
| **Total** |                                | **~6–8 weeks** |

Phases 1 and 2 can partially overlap after Phase 0. Phase 4 can start once write fan-out APIs are stable.

---

## 10. API & MCP Surface

### Minimal changes to existing tools

| Tool / Endpoint     | Change                                                                 |
|---------------------|------------------------------------------------------------------------|
| `remember` / POST   | Accept optional structured `kv_triples` / `graph_triples`; still auto-extract if omitted |
| `recall` / search   | Returns fused results; supports `explain`, optional `as_of`            |
| `emit`              | Unchanged (worker does the hybrid write)                               |
| `update` / PATCH    | Re-embed if content changes; refresh KV/Graph as needed                |
| `forget` / DELETE   | Cascade or soft-delete secondary rows                                  |

### New optional parameters

```
search(
  query: str,
  filters: { org implied by key, session_id?, ... },
  top_k?: int,
  explain?: bool,
  as_of?: datetime,          # temporal
  scopes?: ["user"|"session"|"agent"]
)
```

Keep the MCP tool surface simple; advanced parameters stay on the HTTP API first.

---

## 11. Success Metrics

### Quality

- Fact-lookup accuracy (preference, city, decision, config) measurably higher than vector-only baseline
- Relationship / multi-hop questions return relevant connected memories
- Soft-invalidated edges correctly excluded from “current” queries and included in `as_of` history queries
- Dedup rate remains healthy (no explosion of near-duplicates)

### Performance

- p95 recall latency remains acceptable under hybrid load (target: < 150–200 ms for typical org sizes with in-process embeddings)
- Per-store latency visible in metrics / explain

### Correctness & safety

- Zero cross-org leakage in automated tests
- Graph edge count growth stays within configured caps under synthetic noisy extraction
- Feature flags can fully disable KV/Graph and restore prior behaviour

### Product

- `explain=true` is useful for debugging ranking
- Fusion weights are configurable and documented
- MCP tools remain simple for Cursor / Claude Code / OpenCode users

---

## 12. Non-Goals for v2

- Full Neo4j / Memgraph deployment (Postgres graph tables are sufficient for v2; interface allows a later swap)
- Redis / external KV service (Postgres table is enough)
- Learned fusion weights or cross-encoder reranker as default (optional later)
- Automatic full temporal versioning of every vector/KV fact (graph temporal is the priority)
- Breaking changes to existing MCP tool names or auth model

---

## 13. Risks & Mitigations

| Risk                              | Likelihood | Impact | Mitigation                                              |
|-----------------------------------|------------|--------|---------------------------------------------------------|
| Extraction quality too noisy      | Medium     | High   | Caps, confidence thresholds, heuristic fallback         |
| Latency regression from 3 stores  | Medium     | High   | Parallelism, indexes, explain latency breakdown         |
| KV fact_type explosion            | Medium     | Medium | Allow-list + audit                                      |
| Graph becomes dense / slow        | Medium     | Medium | Hop limit, caps, valid-only default indexes             |
| Embedding drift over time         | Low–Med    | Medium | Periodic re-embed of hot memories                       |
| Scope bugs across new tables      | Low        | High   | Repository-level org_id enforcement + tests             |

---

## 14. Implementation Order (Concrete First Tickets)

1. **Phase 0**
   - Storage protocol definitions
   - Feature flags + config
   - Explain response shape skeleton

2. **Phase 1**
   - `kv_facts` migration
   - KV repository + service
   - Wire write path + basic key derivation on search
   - Tests for preference / city style lookups

3. **Phase 2**
   - `graph_nodes` / `graph_edges` migration
   - Soft-invalidation edge logic
   - Neighbor expansion + memory linking
   - Tests for city-change and multi-hop

4. **Phase 3**
   - Parallel fusion orchestrator
   - Weight config + full explain
   - Latency metrics

5. **Phase 4**
   - Extractor schema + prompt update
   - End-to-end hybrid write tests

6. **Phase 5**
   - Caps, audits, re-embed job, docs, dashboard views

---

## 15. References

- Hybrid Memory lesson (Vector + Graph + KV):  
  https://github.com/rohitg00/ai-engineering-from-scratch/tree/main/phases/14-agent-engineering/09-hybrid-memory-mem0
- Mem0 paper: Chhikara et al., *Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory* (arXiv:2504.19413)
- Mem0 docs (hybrid retrieval, entity linking, temporal): https://docs.mem0.ai
- Current Memoria architecture specs: `spec/03-architecture.md`, `spec/06-database.md`, `spec/07-phase3-intelligence.md`

---

## 16. Appendix — Example Fusion Behaviour

**Write sequence**

```
add("ava lives in Berlin", kv=[("city","Berlin")], graph=[("ava","lives_in","Berlin")])
add("ava moved to Lisbon last month", kv=[("city","Lisbon")], graph=[("ava","lives_in","Lisbon")])
```

**Graph state after second write**

```
ava --lives_in--> Berlin   [valid=false, valid_to=T2]
ava --lives_in--> Lisbon   [valid=true]
```

**Search: “where does ava live?” (current)**  
→ Lisbon memory ranked highest (KV exact + valid graph edge + recency)

**Search: “where did ava live before?” / `as_of=T1`**  
→ Berlin memory can still be returned via historical graph edge

**Search: “what is ava building?”**  
→ Relies more on vector + any project KV/graph triples

This is the behaviour v2 is designed to deliver.
