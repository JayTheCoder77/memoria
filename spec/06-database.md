# Database Structure

Single Postgres instance (with pgvector extension) is the source of truth for
everything — relational metadata and embeddings live together, per the MVP
decision in `spec/00-plan.md`. There is no cache layer (dropped — see
`spec/03-architecture.md` for the reasoning); reads go directly against Postgres.
The web app owns no database of its own — it's a stateless client of the Memory
API, authenticated via the session JWT cookie (see `spec/05-auth.md`).

## Layer summary

| Layer | Owns data? | Storage |
|---|---|---|
| Web app (`apps/web`) | No | None — stateless client, session JWT in httpOnly cookie |
| Memory API (`apps/memory-api`) | Yes — all of it | Postgres (+pgvector) only |
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
| key_last4 | text | last 4 chars of the raw key, display only (e.g. `mem_...ab12`) — dropped the live/test prefix split, unnecessary for a single-key-per-org MVP |
| revoked_at | timestamptz, nullable | null = active |
| last_used_at | timestamptz, nullable | updated on each successful auth — needed for the "last used" column already speced in `spec/design/05-dashboard.md` |
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
| updated_at | timestamptz, nullable | set on `PATCH /memories/{id}` — distinct from `last_accessed_at`, which only moves on recall |
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
Since there's no cache absorbing read cost, these indexes are the actual speed
budget for recall — worth tuning deliberately rather than accepting pgvector
defaults.

- `api_keys.key_hash` — unique index (lookup on every machine-auth request)
- `users.google_id`, `users.email` — unique indexes
- `memories(org_id, session_id)` — composite index, primary scoping filter on
  every recall; narrows the candidate set *before* the vector search runs
- `memories.embedding` — pgvector index. Start with `ivfflat` for MVP simplicity;
  move to `hnsw` once data volume grows, since `hnsw` gives better query latency
  at the cost of slower/heavier index builds — worth the tradeoff once recall
  latency (not build time) is the thing users feel
- `event_buffer(status, created_at)` — composite index for the worker's polling query

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
        text key_last4
        timestamptz revoked_at
        timestamptz last_used_at
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
        timestamptz updated_at
    }
    EVENT_BUFFER {
        uuid id PK
        uuid org_id FK
        text session_id
        text event_type
        jsonb payload
        enum status
    }
