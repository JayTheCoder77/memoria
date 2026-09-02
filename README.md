# Memoria

An agentic memory layer for MCP-compatible harnesses (Cursor, Claude Code, and others).
The Memory API owns storage and retrieval; the MCP server is a thin adapter.

## Stack

- **Memory API** — Python / FastAPI (`apps/memory-api`)
- **MCP server** — Python (`apps/mcp-server`)
- **Web** — Next.js (`apps/web`)
- **Postgres + pgvector** — local via Docker Compose

## Prerequisites

- Node 24+ and [Bun](https://bun.sh)
- [uv](https://docs.astral.sh/uv/) and Python 3.12+
- Docker

## Local setup

Copy each app's `.env.example` to `.env` (or `.env.local` for the web app) and fill in values:

```bash
cp apps/memory-api/.env.example apps/memory-api/.env
cp apps/mcp-server/.env.example apps/mcp-server/.env
cp apps/web/.env.example apps/web/.env.local
```

Then:

```bash
bun install

docker compose -f infra/docker-compose.yml up -d

cd apps/memory-api
uv sync
uv run alembic upgrade head
uv run uvicorn memory_api.main:app --reload --port 8000
uv run python -m memory_api.worker   # optional: drain event_buffer
```

From the repo root, `bun run dev` starts Turbo tasks for apps that define a `dev` script.

## Tests

```bash
cd apps/memory-api
uv run pytest
```

API tests skip Postgres cases if the database is not running.

## Auth (Google OAuth)

Register an OAuth 2.0 Web client in Google Cloud Console (authorized redirect
`http://localhost:3000/api/auth/callback/google`). Put the client ID and secret in
`apps/web/.env.local` (`AUTH_GOOGLE_ID`, `AUTH_GOOGLE_SECRET`, `NEXTAUTH_SECRET`)
and the same client ID in `apps/memory-api/.env` as `MEMORIA_GOOGLE_CLIENT_ID`.

`MEMORIA_EMBEDDER=minilm` switches the Memory API to in-process MiniLM
(`uv sync --extra minilm` in `apps/memory-api`). Extraction uses each org’s
OpenRouter key from dashboard Settings (BYOK). With no key, the worker uses
the heuristic extractor.

Recall latency:

```bash
uv run python scripts/bench_recall.py --api-key mem_... --n 50
```

## MCP server

```bash
cd apps/memory-api
uv run python -m memory_api.cli issue-key --org-name local

cd apps/mcp-server
uv sync
uv run python -m mcp_server
```

Machine auth is a `mem_...` Bearer token. Put it in the MCP process as
`MEMORY_API_KEY` (OpenCode `environment`, Cursor `env`, or `apps/mcp-server/.env`).
The tools `remember`, `recall`, `update`, `forget`, and `emit` do not take an API
key. Org is implied by the key. Pass `session_id` per conversation, or set
`MEMORY_SESSION_ID`. `emit` queues events for extraction; it does not always
create a memory.

## Specs

Product and architecture live in `spec/`. Web UI details live in `apps/web/web-spec/`.
