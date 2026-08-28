# Agentic Memory Layer — MVP Plan

## Vision
An agentic memory layer that gives AI agent harnesses (Claude Code, Cursor, Aider,
custom LangGraph agents) fast, intelligent recall across sessions — episodic events,
durable facts, and learned fixes — exposed as an MCP server so any compatible harness
can plug in without custom integration work.

## Goals (MVP)
- Sub-second (target sub-100ms cached) recall latency on the read path
- Async, non-blocking write path so memory extraction never slows the harness loop
- Three memory types: episodic, semantic, procedural
- Dedup/consolidation so the store doesn't bloat and degrade retrieval quality
- Exposed via an MCP server (`remember`, `recall`, `forget`) usable by any MCP-compatible harness
- Multi-tenant from day one (org_id / session_id scoping) — not bolted on later

## Non-goals (MVP)
- No graph DB / entity-relationship modeling (fast-follow)
- No billing/usage metering
- No fine-grained permissions beyond org-level isolation
- No custom per-harness integrations beyond MCP (SDKs come later)

## Stack decisions
- **Language preference: Python first, TypeScript second.** Core service and MCP
  server are Python. TypeScript is scoped to the web dashboard/landing page only.
- **Monorepo:** Turborepo, orchestrating polyglot apps (Python apps wrapped with a
  thin `package.json` so `turbo` can run their tasks alongside the TS app).
- **Storage:** Postgres + pgvector (single DB for metadata + embeddings in MVP).
- **Cache:** Redis, fronting the read path for hot/recent/frequent memories.
- **Embeddings:** small, fast embedding model — latency matters more than max quality here.
- **Extraction:** batched LLM pass over event buffers, not per-message.

## Phases

### Phase 1 — Core service (Week 1)
FastAPI app, Postgres+pgvector schema, embeddings pipeline, basic write/read REST endpoints.

### Phase 2 — Speed + retrieval quality (Week 2)
Hybrid retrieval scoring (semantic + recency decay + importance), Redis cache layer,
MCP server wrapping the core service's `remember`/`recall`/`forget`.

### Phase 3 — Intelligence (Week 3)
Batched extraction pipeline turning raw events into memories, dedup/consolidation job,
minimal dashboard to inspect stored memories.

## Success criteria for MVP
- A harness can call `remember()` and `recall()` through MCP against a running instance
- p95 read latency measured and documented (even if not yet optimized to target)
- Duplicate/near-duplicate memories are collapsed automatically
- Multi-tenant isolation verified (org A cannot recall org B's memories)
