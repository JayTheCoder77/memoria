# Database Structure

Single Postgres instance (with pgvector extension) is the source of truth for
everything — relational metadata and embeddings live together, per the MVP
decision in `spec/00-plan.md`. Redis is a cache, not a source of truth, and is
included here for completeness since it's still part of the data layer. The web
app owns no database of its own — it's a stateless client of the Memory API,
authenticated via the session JWT cookie (see `spec/05-auth.md`).

## Layer summary

| Layer | Owns data? | Storage |
|---|---|---|
| Web app (`apps/web`) | No | None — stateless client, session JWT in httpOnly cookie |
| Memory API (`apps/memory-api`) | Yes — all of it | Postgres (+pgvector), Redis (cache only) |
| MCP server (`apps/mcp-server`) | No | None — stateless adapter |
| Extraction Worker | No (writes via Memory API's DB layer) | Same Postgres instance |

## Postgres schema

### `orgs`
| Column | Type | Notes |
|---|---|---|
| id | uuid, PK | |
| name | text | |
| created_at | timestamptz | |

### `users`
| Column | Type | Notes |
|---|---|---|
| id | uuid, PK | |
| org_id | uuid, FK → orgs.id | |
| google_id | text, unique | from Google OAuth claims |
| email | text, unique | |
| name | text | |
| created_at | timestamptz | |

### `api_keys`
| Column | Type | Notes |
|---|---|---|
| id | uuid, PK | |
| org_id | uuid, FK → orgs.id | |
| created_by_user_id | uuid, FK → users.id | |
| key_hash | text, unique | hashed, never plaintext |
| prefix | text | `live` / `test` |
| revoked_at | timestamptz, nullable | null = active |
| created_at | timestamptz | |

### `memories`
| Column | Type | Notes |
|---|---|---|
| id | uuid, PK | |
| org_id | uuid, FK → orgs.id | enforced at query layer on every read/write |
| session_id | text | client-supplied scoping value (per-repo/per-agent-session), not an auth mechanism |
| memory_type | enum | `episodic` / `semantic` / `procedural` |
| content | text | the memory itself |
| embedding | vector(N) | pgvector column, N = embedding model dimension |
| importance | float | feeds retrieval scoring |
| access_count | int, default 0 | incremented on recall, feeds importance/decay |
| source_metadata | jsonb | e.g. originating tool call, file path, event id |
| created_at | timestamptz | |
| last_accessed_at | timestamptz, nullable | updated on recall |

### `event_buffer`
Durable queue for the write path — a Postgres table is enough for MVP, avoids
standing up Kafka/SQS before there's a reason to.

| Column | Type | Notes |
|---|---|---|
| id | uuid, PK | |
| org_id | uuid, FK → orgs.id | |
| session_id | text | |
| event_type | text | message / tool_call / diff |
| payload | jsonb | raw harness event |
| status | enum | `pending` / `processing` / `processed` / `failed` |
| created_at | timestamptz | |
| processed_at | timestamptz, nullable | |

## Indexes
- `api_keys.key_hash` — unique index (lookup on every machine-auth request)
- `users.google_id`, `users.email` — unique indexes
- `memories(org_id, session_id)` — composite index, primary scoping filter on every recall
- `memories.embedding` — pgvector index (start with `ivfflat`; move to `hnsw` if
  recall quality/latency demands it once data volume grows)
- `event_buffer(status, created_at)` — composite index for the worker's polling query

## Redis (cache layer, not source of truth)
- Key pattern: `cache:{org_id}:{query_hash}` → serialized top-k recall results
- TTL-based expiry (pick a value, e.g. 5 min, for MVP) rather than precise
  invalidation-on-write — simpler and acceptable given eventual consistency is fine here
- No durability requirements — a cold cache just means the next read falls through to Postgres

## Entity relationship diagram

```mermaid
erDiagram
    ORGS ||--o{ USERS : has
    ORGS ||--o{ API_KEYS : has
    ORGS ||--o{ MEMORIES : has
    ORGS ||--o{ EVENT_BUFFER : has
    USERS ||--o{ API_KEYS : creates

    ORGS {
        uuid id PK
        text name
        timestamptz created_at
    }
    USERS {
        uuid id PK
        uuid org_id FK
        text google_id
        text email
        text name
    }
    API_KEYS {
        uuid id PK
        uuid org_id FK
        uuid created_by_user_id FK
        text key_hash
        text prefix
        timestamptz revoked_at
    }
    MEMORIES {
        uuid id PK
        uuid org_id FK
        text session_id
        enum memory_type
        text content
        vector embedding
        float importance
        int access_count
        jsonb source_metadata
    }
    EVENT_BUFFER {
        uuid id PK
        uuid org_id FK
        text session_id
        text event_type
        jsonb payload
        enum status
    }
