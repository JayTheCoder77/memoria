# Todo List

## Phase 0 — Repo setup
- [ ] Init Turborepo root (`package.json`, `turbo.json`, workspace config)
- [ ] Scaffold `apps/memory-api` (Python, FastAPI, `pyproject.toml`)
- [ ] Scaffold `apps/mcp-server` (Python, MCP SDK, `pyproject.toml`)
- [ ] Scaffold `apps/web` (TypeScript, Next.js)
- [ ] `infra/docker-compose.yml` — Postgres+pgvector, Redis, local dev
- [ ] Shared config packages (ruff config for Python, eslint/tsconfig for TS)
- [ ] Root README with setup instructions

## Phase 1 — Core service
- [ ] Postgres schema: `memories` table (id, org_id, session_id, memory_type, content,
      embedding, importance, created_at, last_accessed_at, access_count)
- [ ] Alembic migrations set up
- [ ] Embedding pipeline (single function: text → vector)
- [ ] `POST /memories` — write endpoint
- [ ] `GET /memories/search` — basic vector similarity read endpoint (no scoring yet)
- [ ] `DELETE /memories/{id}` — forget endpoint
- [ ] Multi-tenant scoping enforced at the query layer (org_id required on every call)
- [ ] Basic test suite (write → read round trip, tenant isolation test)

## Phase 2 — Speed + retrieval
- [ ] Retrieval scoring: combine semantic similarity + recency decay + importance weight
- [ ] Redis cache layer in front of `GET /memories/search`
- [ ] Cache invalidation strategy on write (or TTL-based, pick one for MVP)
- [ ] Token-budget-aware top-k truncation on recall responses
- [ ] Latency benchmark script (p50/p95 on read path, cached vs uncached)
- [ ] MCP server: `remember` tool → calls `POST /memories`
- [ ] MCP server: `recall` tool → calls `GET /memories/search`
- [ ] MCP server: `forget` tool → calls `DELETE /memories/{id}`
- [ ] Define MCP tool schemas so `org_id`/`session_id`/auth are required arguments
      on every call (no server-side session state to fall back on)
- [ ] End-to-end test: connect a harness to the MCP server locally, verify round trip

## Phase 3 — Intelligence
- [ ] Event buffer/queue for incoming harness events (session messages, tool calls, diffs)
- [ ] Batched extraction job (cheap/fast LLM pass, runs every N events or on session end)
- [ ] Embedding-similarity dedup check before insert
- [ ] Consolidation job (merge near-duplicate memories, promote recurring patterns)
- [ ] Minimal dashboard page: list memories by org/session, filter by type
- [ ] Manual review flow for extracted memories (optional, if time allows)

## Phase 4 — Launch prep
- [ ] One-pager landing page (hero, how it works, quickstart, MCP config snippet)
- [ ] Public docs: quickstart, MCP config example, API reference
- [ ] Deploy core service + MCP server (single environment is fine for MVP)
- [ ] Record a short demo (connect Claude Code or Cursor to the MCP server live)
