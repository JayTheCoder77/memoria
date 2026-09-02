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

```bash
bun install

docker compose -f infra/docker-compose.yml up -d

cd apps/memory-api
uv sync
uv run alembic upgrade head
uv run uvicorn memory_api.main:app --reload --port 8000
```

From the repo root, `bun run dev` starts Turbo tasks for apps that define a `dev` script.

## Tests

```bash
cd apps/memory-api
uv run pytest
```

API tests expect Docker (they start a pgvector Postgres container).

## Specs

Product and architecture live in `spec/`. Web UI details live in `apps/web/web-spec/`.
