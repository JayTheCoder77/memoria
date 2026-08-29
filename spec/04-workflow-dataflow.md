# Workflow & Dataflow

## Write path (async, off the hot path)

Events are buffered and processed in batches — never per-message — to keep the
harness loop unaffected by extraction cost.

```mermaid
sequenceDiagram
    participant Harness
    participant Queue as Event Buffer/Queue
    participant Worker as Extraction Worker
    participant LLM as Fast/cheap LLM
    participant DB as Postgres+pgvector

    Harness->>Queue: emit event (message, tool call, diff)
    Note over Queue: batched every N events / on session end
    Queue->>Worker: batch of events
    Worker->>LLM: extract candidate memories
    LLM-->>Worker: candidate memory list
    Worker->>DB: check embedding similarity (dedup)
    alt duplicate found
        Worker->>DB: update existing memory (importance/access_count)
    else new memory
        Worker->>DB: insert memory + embedding
    end
```

## Read path (sync, latency-critical)

Direct against Postgres+pgvector, no cache layer. This is the path that must
stay fast, since it sits directly in the harness's turn loop — the two levers
for that are the in-process embedding model (no network round-trip) and a
well-tuned pgvector index (see `spec/06-database.md`), not a cache.

```mermaid
sequenceDiagram
    participant Harness
    participant MCP as MCP Server
    participant API as Memory API
    participant Embed as Local Embedding Model
    participant DB as Postgres+pgvector

    Harness->>MCP: recall(query)
    MCP->>API: GET /memories/search
    API->>Embed: embed query (in-process, no network call)
    Embed-->>API: query vector
    API->>DB: vector similarity search (scoped to org_id/session_id)
    DB-->>API: candidate memories
    API->>API: score (semantic + recency + importance)
    API-->>MCP: top-k memories (token-budgeted)
    MCP-->>Harness: recall results
```

## Update path (sync, explicit correction)

A direct way to fix a memory's content or metadata — separate from the extraction
worker's implicit dedup-driven updates. Useful for a harness correcting something
it got wrong, or a human editing from the dashboard.

```mermaid
sequenceDiagram
    participant Caller as Harness or Dashboard
    participant MCP as MCP Server (harness only)
    participant API as Memory API
    participant Embed as Local Embedding Model
    participant DB as Postgres+pgvector

    Caller->>MCP: update(memory_id, content?, importance?, memory_type?)
    MCP->>API: PATCH /memories/{id}
    API->>API: verify memory belongs to caller's org_id
    alt content changed
        API->>Embed: re-embed new content (in-process)
        Embed-->>API: new vector
    end
    API->>DB: update row (fields + updated_at)
    DB-->>API: confirmation
    API-->>MCP: updated memory
    MCP-->>Caller: confirmation
```

Note: the dashboard calls `PATCH /memories/{id}` directly (session-JWT
authenticated, no MCP hop needed) since it's already talking to the Memory API.

## Data lifecycle notes
- `last_accessed_at` and `access_count` update on every successful recall — this
  feeds the importance weight in scoring and the consolidation job's decisions.
- Memories with no access over a defined window are candidates for decay/archival
  (fast-follow, not required for MVP correctness).
- With no cache, every recall is a live query — this is intentional (see
  `spec/03-architecture.md` for why the cache was dropped) and means results
  are always current, no staleness/invalidation logic to maintain.
