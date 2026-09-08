# Memoria

An agentic memory layer for MCP-compatible harnesses (Cursor, Claude Code, and others).
The Memory API owns storage and retrieval; the MCP server is a thin adapter.

## Stack

- **Memory API** — Python / FastAPI (`apps/memory-api`)
- **MCP server** — Python (`apps/mcp-server`)
- **Web** — Next.js (`apps/web`)
- **Postgres + pgvector** — local via Docker Compose
- **REST clients** — Python SDK + CLI (`packages/memoria-cloud-sdk`, `packages/memoria-cloud-cli`) and Node SDK (`packages/memoria-cloud-js`)

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

cd apps/mcp-server
uv run pytest

cd packages/memoria-cloud-sdk
uv run pytest

cd packages/memoria-cloud-cli
uv run pytest

cd packages/memoria-cloud-js
bun test
```

API tests skip Postgres cases if the database is not running.

## Auth (Google OAuth)

Register an OAuth 2.0 Web client in Google Cloud Console (authorized redirect
`http://localhost:3000/api/auth/callback/google`). Put the client ID and secret in
`apps/web/.env.local` (`AUTH_GOOGLE_ID`, `AUTH_GOOGLE_SECRET`, `NEXTAUTH_SECRET`)
and the same client ID in `apps/memory-api/.env` as `MEMORIA_GOOGLE_CLIENT_ID`.

`MEMORIA_EMBEDDER=hf` uses Hugging Face Inference for MiniLM (needs `MEMORIA_HF_TOKEN`).
`MEMORIA_EMBEDDER=minilm` runs MiniLM in-process (`uv sync --extra minilm`). Do not mix
embedders on one database. Extraction uses each org’s keys from dashboard Settings
(BYOK): OpenRouter first, then Groq as fallback (model fixed to
`openai/gpt-oss-20b` — not selectable). With no keys, the worker uses the
heuristic extractor.

Recall latency:

```bash
uv run python scripts/bench_recall.py --api-key mem_... --n 50
```

## MCP server

Local checkout:

```bash
cd apps/mcp-server
uv sync
uv run memoria-mcp
```

Other users (no clone): install [uv](https://docs.astral.sh/uv/) so `uvx` is on your PATH, then paste a snippet.

macOS / Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows (PowerShell):

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Restart the terminal (and Cursor / OpenCode) so `uvx` is found. Check with `uvx --version`. Create a `mem_...` key in the dashboard and put it in MCP env — not in prompts or AGENTS.md.

Cursor / Claude Code (`mcp.json` / Claude MCP settings):

```json
{
  "mcpServers": {
    "memoria": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/JayTheCoder77/memoria.git#subdirectory=apps/mcp-server",
        "memoria-mcp"
      ],
      "env": {
        "MEMORY_API_URL": "https://memoria-api-jw5g.onrender.com",
        "MEMORY_API_KEY": "mem_..."
      }
    }
  }
}
```

OpenCode (`opencode.json` in the project, or `~/.config/opencode/opencode.json`):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "memoria": {
      "type": "local",
      "command": [
        "uvx",
        "--from",
        "git+https://github.com/JayTheCoder77/memoria.git#subdirectory=apps/mcp-server",
        "memoria-mcp"
      ],
      "enabled": true,
      "timeout": 60000,
      "environment": {
        "MEMORY_API_URL": "https://memoria-api-jw5g.onrender.com",
        "MEMORY_API_KEY": "mem_..."
      }
    }
  }
}
```

Machine auth is a `mem_...` Bearer token. Put it in the MCP process as
`MEMORY_API_KEY`. Tools do not take an API key. Org is implied by the key.

| Tool | What it does |
|---|---|
| `remember` | Immediate save of caller text. Deduped. Then KV + graph via OpenRouter → Groq (`openai/gpt-oss-20b`) → regex. Use when a fact must persist now. |
| `emit` | Queue only (`message`, `tool_call`, `diff`, `session_end`). MCP instructions tell the agent to emit after user turns. Noisy tools skipped. Worker extracts later (same cascade). Flushes at 10 events or `session_end`. |
| `recall` | Fused search: vector + KV + graph. Optional `as_of`. Query keys: OpenRouter if configured, else regex. |
| `update` | Patch content, importance, or type. Re-embeds content. Does not rewrite KV/graph. |
| `forget` | Delete one memory. KV cascade-deletes; graph `memory_id` is set null. |

Do not set `MEMORY_SESSION_ID` in MCP JSON. Writes get an auto session id for the harness process; it rotates after `session_end`. `recall` searches the whole org unless you pass `session_id`. Delete `MEMORY_SESSION_ID` from existing configs if it is still `local`.

## REST SDKs and CLI

Same `mem_...` key as MCP. Default API URL is `https://memoria-api-jw5g.onrender.com`.
Published as `memoria-cloud-sdk` on [PyPI](https://pypi.org/project/memoria-cloud-sdk/)
and [npm](https://www.npmjs.com/package/memoria-cloud-sdk), and `memoria-cloud-cli`
on [PyPI](https://pypi.org/project/memoria-cloud-cli/).

`q` is the search question in plain language (not SQL). `session_id` is a label you
choose for a chat or project; omit it on recall to search the whole org.

```bash
pip install memoria-cloud-sdk
pip install memoria-cloud-cli   # console script: memoria-cloud
npm install memoria-cloud-sdk   # or: bun add memoria-cloud-sdk
```

```python
from memoria_cloud import Memoria

client = Memoria()  # MEMORY_API_URL / MEMORY_API_KEY
client.remember(content="We prefer pytest", session_id="s1")
hits = client.recall(q="what test runner do we use?")
```

```ts
import { Memoria } from "memoria-cloud-sdk";

const client = new Memoria();
await client.recall({ q: "what test runner do we use?" });
```

```bash
export MEMORY_API_KEY=mem_...
memoria-cloud recall "what test runner do we use?"
memoria-cloud remember "We prefer pytest" --session s1
```

Field-by-field usage is in the website docs: `/docs/sdk` and `/docs/cli`.

## Hosted deploy (free-tier)

- **Neon** — Postgres. Enable `vector` (Alembic does `CREATE EXTENSION IF NOT EXISTS vector`). Use the pooled connection string as `MEMORIA_DATABASE_URL` (or `DATABASE_URL`).
- **Render** — Memory API. Blueprint: `render.yaml`. Free web service sleeps after idle; `MEMORIA_RUN_WORKER=true` runs extraction in-process (Render has no free background workers). Do not also run `python -m memory_api.worker` on the same instance.
- **Vercel** — `apps/web`. Root directory `apps/web`. Set `MEMORY_API_URL` and `NEXT_PUBLIC_MEMORY_API_URL` to `https://memoria-api-jw5g.onrender.com`, plus Google OAuth (`AUTH_GOOGLE_ID`, `AUTH_GOOGLE_SECRET`, `NEXTAUTH_SECRET`, `NEXTAUTH_URL`).
- **Hugging Face** — token with Inference Providers access as `MEMORIA_HF_TOKEN` on Render.
- **Google Cloud Console** — add `https://YOUR-WEB.vercel.app/api/auth/callback/google` and `http://localhost:3000/api/auth/callback/google`.
- **MCP** — stays on the user’s machine via `uvx` as above. Not deployed.

Set `MEMORIA_CORS_ORIGINS` to the Vercel origin if the browser ever calls the API directly. Dashboard calls are server-side and do not need CORS.

## Specs

Product and architecture live in `spec/`. Hybrid stores, fusion weights, and
failure modes are in `spec/03-architecture.md` and `spec/v2-phase5-hardening.md`.
Web UI details live in `apps/web/web-spec/`.
