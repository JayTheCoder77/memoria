# Todo List

## Phase 0 — Repo setup
- [x] Init Turborepo root (`package.json`, `turbo.json`, workspace config)
- [x] Scaffold `apps/memory-api` (Python, FastAPI, `pyproject.toml`)
- [x] Scaffold `apps/mcp-server` (Python, MCP SDK, `pyproject.toml`)
- [x] Scaffold `apps/web` (TypeScript, Next.js)
- [x] `infra/docker-compose.yml` — Postgres+pgvector, local dev
- [x] Shared config packages (ruff config for Python, eslint/tsconfig for TS)
- [x] Root README with setup instructions

## Phase 1 — Core service
- [x] Postgres schema: `memories` table (id, org_id, session_id, memory_type, content,
      embedding, importance, created_at, last_accessed_at, access_count)
- [x] Alembic migrations set up
- [x] Embedding pipeline (single function: text → vector)
- [x] `POST /memories` — write endpoint
- [x] `GET /memories/search` — basic vector similarity read endpoint (no scoring yet)
- [x] `PATCH /memories/{id}` — update endpoint (content/importance/memory_type; re-embeds if content changes)
- [x] `DELETE /memories/{id}` — forget endpoint
- [x] Multi-tenant scoping enforced at the query layer (org_id required on every call)
- [x] Basic test suite (write → read round trip, tenant isolation test)

## Phase 2 — Speed + retrieval
- [x] Retrieval scoring: combine semantic similarity + recency decay + importance weight
- [x] pgvector index tuning (`ivfflat` to start) + `(org_id, session_id)` composite index
- [x] In-process embedding model wired into both read and write paths
- [x] Token-budget-aware top-k truncation on recall responses
- [x] Latency benchmark script (p50/p95 on the direct-query read path)
- [x] MCP server: `remember` tool → calls `POST /memories`
- [x] MCP server: `recall` tool → calls `GET /memories/search`
- [x] MCP server: `update` tool → calls `PATCH /memories/{id}`
- [x] MCP server: `forget` tool → calls `DELETE /memories/{id}`
- [x] Define MCP tool schemas so `org_id`/`session_id`/auth are required arguments
      on every call (no server-side session state to fall back on)
- [x] API key auth: hashing/validation middleware on Memory API (see `spec/05-auth.md`)
- [x] API key auth: rate limiting keyed to API key
- [x] Google OAuth app registration (client ID/secret)
- [x] `POST /auth/google` — verify ID token, find-or-create user + org, issue session JWT
- [x] Session JWT validation middleware for dashboard-only routes
- [x] `users` / `orgs` tables + migrations
- [x] `memories` table + pgvector index (ivfflat) + composite `(org_id, session_id)` index
- [x] `event_buffer` table + status/created_at index for worker polling
- [x] Web app: Google sign-in page (Auth.js), key management page (create/revoke)
- [x] End-to-end test: connect a harness to the MCP server locally, verify round trip

## Phase 3 — Intelligence
- [x] Event buffer/queue for incoming harness events (session messages, tool calls, diffs)
- [x] Batched extraction job (cheap/fast LLM pass, runs every N events or on session end)
- [x] Embedding-similarity dedup check before insert
- [x] Consolidation job (merge near-duplicate memories, promote recurring patterns)
- [x] Minimal dashboard page: list memories by org/session, filter by type
- [ ] Manual review flow for extracted memories (optional, if time allows)

## Phase 4 — Launch prep
- [x] One-pager landing page (hero, how it works, quickstart, MCP config snippet)
- [x] Public docs: quickstart, MCP config example, API reference
- [ ] Deploy core service + MCP server (single environment is fine for MVP)
- [ ] Record a short demo (connect Claude Code or Cursor to the MCP server live)
