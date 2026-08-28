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

Cache-first. This is the path that must stay fast, since it sits directly in the
harness's turn loop.

```mermaid
sequenceDiagram
    participant Harness
    participant MCP as MCP Server
    participant API as Memory API
    participant Cache as Redis
    participant DB as Postgres+pgvector

    Harness->>MCP: recall(query)
    MCP->>API: GET /memories/search
    API->>Cache: check cache (org_id, query_hash)
    alt cache hit
        Cache-->>API: cached results
    else cache miss
        API->>DB: vector similarity search
        DB-->>API: candidate memories
        API->>API: score (semantic + recency + importance)
        API->>Cache: populate cache
    end
    API-->>MCP: top-k memories (token-budgeted)
    MCP-->>Harness: recall results
```

## Data lifecycle notes
- `last_accessed_at` and `access_count` update on every successful recall — this
  feeds the importance weight in scoring and the consolidation job's decisions.
- Memories with no access over a defined window are candidates for decay/archival
  (fast-follow, not required for MVP correctness).
- Cache entries are invalidated (or short-TTL'd) on any write to the same
  `org_id`/`session_id` to avoid serving stale recall results.
