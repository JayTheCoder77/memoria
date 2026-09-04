# Memoria v2 Phase 1 — KV Store

**Status:** Ready for implementation  
**Parent:** `spec/v2_extension_plan.md`  
**Depends on:** `spec/v2-phase0-foundations.md`  
**Date:** 2026-09-04

Phase 1 adds a Postgres `KVStore` so exact fact lookups (preference, city, decision, language) can surface memories even when vector ranking is weak. Canonical rows stay in `memories`. Graph stays no-op.

## Goal

With `MEMORIA_ENABLE_KV` on (the new default), a successful remember can write `kv_facts`, and search unions KV hits with vector hits. `relevance = max(vector_similarity, kv_match)`. Existing remember/search contracts stay the same when no triples match.

## Non-goals

- No `graph_nodes` / `graph_edges`, graph fusion, or `as_of`
- No hard `fact_type` allow-list table or enum constraint
- No dashboard views for KV keys
- No MCP schema change for `explain` / `kv_triples` (HTTP first; MCP still posts `content`)
- No `entities` / `embedding_model` / `embedding_version` columns on `memories`
- No full Phase 3 parallel orchestrator service — keep wiring in persist + search router

## Decisions (locked)

| Topic | Choice |
|-------|--------|
| Scope | Full Phase 1: table, `PostgresKVStore`, extraction triples, write fan-out, search union+boost |
| Ingest | Explicit `kv_triples` when present; otherwise conservative heuristic on `content` |
| Search mix | Union by `memory_id`; KV-only hits allowed (`vector_similarity = 0`) |
| Flag | `enable_kv` defaults **true**; `enable_graph` stays false |
| `fact_type` | Open string set; extractors seed preference / city / decision / language |
| Query keys | **LLM first** when the org has an OpenRouter key; **rules fallback** otherwise or on LLM failure |
| Remember vs KV errors | Memory persist is source of truth. KV failures are **logged and ignored** |

## Architecture

```
POST /memories  or  worker persist_candidate
  → insert or dedup bump on memories
  → if enable_kv: resolve triples → put (savepoint; log+continue on error)
  → return MemoryOut  (unchanged shape)

GET /memories/search
  → embed(q) + vector search (unchanged)
  → derive_kv_candidates(q): LLM if org key else rules; LLM error → rules
  → kv.search_keys(org, candidates)
  → load missing memories by id
  → union by memory_id
  → relevance = max(vector_similarity, kv_match)
  → retrieval_score with existing fusion weights
  → explain: kv_match + sources includes "kv" when KV contributed
```

| Unit | Responsibility | Depends on |
|------|----------------|------------|
| `KvFact` (ORM) | Row mapping for `kv_facts` | `orgs`, `memories` |
| `PostgresKVStore` | `put` upsert, `get`, `search_keys`, `by_org` scoped by `org_id` | SQLAlchemy `Session` |
| `NoOpKVStore` | Used when `enable_kv` is false | — |
| `resolve_kv_triples` | Explicit list, else heuristic parse; cap | `Candidate` / `MemoryCreate` |
| `derive_kv_candidates` | Query → `list[tuple[fact_type, entity]]` | Org OpenRouter key + httpx; rules fallback |
| persist fan-out | After canonical persist; never fails remember | `KVStore` |
| search union | Merge vector rows + KV-linked memories | `KVStore`, `MemoryRepository` |

`PostgresVectorStore` remains unused by the router in this phase (same as Phase 0). Graph stays `NoOpGraphStore`.

## Data model

Alembic revision `0005_kv_facts`, revises `0004_openrouter_byok`.

```sql
CREATE TABLE kv_facts (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        uuid NOT NULL REFERENCES orgs(id),
  memory_id     uuid NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
  user_key      text,
  fact_type     text NOT NULL,
  entity        text NOT NULL,
  value         text,
  importance    float NOT NULL DEFAULT 0.5,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, fact_type, entity)
);

CREATE INDEX idx_kv_facts_org_type ON kv_facts (org_id, fact_type);
CREATE INDEX idx_kv_facts_memory   ON kv_facts (memory_id);
CREATE INDEX idx_kv_facts_org_user ON kv_facts (org_id, user_key) WHERE user_key IS NOT NULL;
```

`put` normalizes `fact_type` and `entity` (`strip` + lowercase). Empty type or entity is skipped. `ON CONFLICT (org_id, fact_type, entity)` updates `memory_id`, `value`, `importance`, `updated_at` (latest wins). `user_key` is unused in Phase 1 callers (pass `None`).

SQLAlchemy model name: `KvFact` in `memory_api.db.models`.

## Config

| Setting | Type | Default |
|---------|------|---------|
| `enable_kv` | bool | `true` |
| `enable_graph` | bool | `false` |
| `kv_max_triples_per_add` | int | `6` |

Update `apps/memory-api/.env.example`: `MEMORIA_ENABLE_KV=true`, document `MEMORIA_KV_MAX_TRIPLES_PER_ADD=6`. Leave fusion weights and graph flag as they are.

Phase 0 tests that asserted `enable_kv is False` must be updated to the new default. Tests that need vector-only search set `enable_kv=False` via env or a fixture.

## Write path

### Triple shape

```python
# On Candidate and MemoryCreate (optional)
kv_triples: list[dict]  # {fact_type: str, entity: str, value?: str | None}
```

LLM extractor JSON:

```json
{"memories":[{
  "content": "...",
  "memory_type": "semantic",
  "importance": 0.75,
  "kv_triples": [{"fact_type":"preference","entity":"typescript","value":null}]
}]}
```

Missing `kv_triples` is valid. Parser skips malformed items.

### Resolve order

1. If the incoming list is non-empty after dropping empty type/entity → use it (truncated to cap).
2. Else run heuristic on `content` only.
3. Heuristic emits at most the cap; seed types: `preference`, `city`, `decision`, `language`.
4. Patterns must be conservative so existing fixtures (e.g. `"explain skeleton probe"`) emit **zero** triples.

### Fan-out

`persist_candidate` still returns `(Memory, inserted: bool)`. After that returns:

- If `not settings.enable_kv`: do nothing.
- Else resolve triples from the candidate; for each, `kv.put(...)` with that memory’s `org_id`, `id`, `importance`.
- Dedup bump (`inserted is False`) **still** writes KV against the existing `memory_id` so facts can attach to a merged row.
- Worker and `POST /memories` share this path. `POST` maps `body.kv_triples` onto `Candidate`.

### KV must not fail remember

Canonical insert/dedup commits (or is already flushed) independently of KV.

Implementation constraint: a failed `INSERT` on the same SQLAlchemy session poisons the transaction. Fan-out **must** use `session.begin_nested()` (savepoint) per `put` or around the KV block. On any exception:

1. The savepoint rolls back (memory row remains).
2. Log `logger.exception("kv fan-out failed")`.
3. Return the `Memory` as if KV were off.

Do not raise to the API client. Do not retry in Phase 1.

`DELETE` on a memory cascades `kv_facts` via FK. No extra forget wiring.

`PATCH` that changes `content` does **not** rewrite KV in Phase 1 (YAGNI; extraction/remember is the write path).

## Read path

When `enable_kv` is false: identical to Phase 0 (no `search_keys`, `kv_match` remains `null` even if `explain=true`).

When `enable_kv` is true:

1. Vector search as today (`repo.search`, over-fetch, score).
2. `candidates = derive_kv_candidates(q, *, api_key, model)`.
3. `facts = kv.search_keys(org_id, candidates)` — exact match on normalized `(fact_type, entity)` pairs. Ignore unknown keys.
4. For facts whose `memory_id` is not already in the vector hit set, `repo.get` (org-scoped). Missing/other-org rows are dropped.
5. Build a map `memory_id → {memory, vector_similarity, kv_match}`.
   - Vector-only: `kv_match` is `null` for explain; treat as `0.0` when computing `max`.
   - KV-only: `vector_similarity = 0.0`, `kv_match = 1.0`.
   - Both: keep real similarity, `kv_match = 1.0`.
6. `relevance = max(vector_similarity, kv_match or 0.0)`.
7. `retrieval_score(similarity=relevance, importance=..., recency=...)`.
8. Sort, `limit`, token-budget truncate.

Exact KV match score is **1.0**. No fuzzy/near-key matching in Phase 1.

### `derive_kv_candidates`

Returns `list[tuple[str, str]]` of `(fact_type, entity)`, normalized the same way as `put`.

**LLM path** (org has decrypted OpenRouter key — same BYOK as the extraction worker):

- One chat completion, `temperature=0`, `response_format=json_object`.
- System prompt asks for candidate lookup keys for the user query, not new memories.
- Expected JSON: `{"keys":[{"fact_type":string,"entity":string}, ...]}`.
- Cap keys at 12 after normalize/dedupe.
- Empty `keys` is valid.

**Rules fallback** (no key, HTTP error, invalid JSON, timeout):

- Log at warning/exception as appropriate; **do not fail search**.
- Tokenize query (lowercase alphanumeric tokens).
- Emit `(seed_type, token)` for each seed type × tokens with length ≥ 3, plus phrase rules: `prefer X` → `("preference", x)`, `lives in X` / `in <city>` → `("city", x)`, `decided X` / `decision` → `("decision", x)`, `language X` → `("language", x)`.
- Cap at 12.

Search tests that must not call the network use hash embedder + no org key (rules path) or inject a fake HTTP client.

Search LLM failure: same as remember — log and continue with rules (or empty rules result). Never 500 because OpenRouter is down.

## Explain

When `explain=true` and KV contributed (`kv_match == 1.0`):

```json
{
  "relevance": 1.0,
  "importance": 0.7,
  "recency": 0.55,
  "sources": ["vector", "kv"],
  "vector_similarity": 0.12,
  "kv_match": 1.0,
  "graph_hops": null,
  "weights": {"relevance": 0.6, "importance": 0.2, "recency": 0.2}
}
```

KV-only hit: `sources: ["kv"]`, `vector_similarity: 0.0`, `kv_match: 1.0`.

Vector-only: `sources: ["vector"]`, `kv_match: null`, `graph_hops: null` (Phase 0 shape).

## Error handling

| Failure | Behaviour |
|---------|-----------|
| KV `put` / unique-constraint / DB error on fan-out | Savepoint rollback, log, remember 201 with memory |
| KV `search_keys` error | Log, treat as no KV hits, return vector ranking |
| LLM candidate derivation error | Log, use rules fallback |
| Rules produce no keys | Vector-only ranking |
| `enable_kv=false` | `NoOpKVStore`; no table writes required for tests that disable the flag |

## Testing

- `PostgresKVStore`: put/get round trip; upsert replaces `memory_id`/value; `search_keys` returns matches; second org cannot read first org’s facts; `by_org` lists org rows.
- Persist: explicit triples written; heuristic preference line writes a triple; `"explain skeleton probe"` writes none; cap 6; dedup bump still upserts KV; `put` raising still returns the memory (savepoint).
- Search: memory with `("preference","typescript")` is returned for query that derives that key even when content is a poor vector match (use hash embedder + distinct strings); `explain` shows `kv_match=1.0` and `"kv"` in `sources`; `enable_kv=false` keeps Phase 0 explain null `kv_match`.
- LLM: `derive_kv_candidates` parses `keys` from a mocked completion; on 500, falls back to rules without raising.
- Extractor: LLM parse accepts optional `kv_triples`; heuristic still returns candidates without triples (resolve fills them at persist).
- Full Memory API suite still passes with default `enable_kv=true`.

## Docs

- Tick Phase 1 boxes in `spec/v2_extension_plan.md`.
- Extend `spec/03-architecture.md` hybrid section: KV is live when the flag is on; Graph still no-op.
- `.env.example` as above.

## Exit criteria

- Fact-lookup queries can return the linked memory via KV union when vector similarity is weak.
- Remember never fails solely because KV or the candidate LLM failed.
- Graph remains off; vector path still works with `MEMORIA_ENABLE_KV=false`.
