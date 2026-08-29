# Folder Structure

Polyglot Turborepo monorepo. Python apps get a thin `package.json` so `turbo` can
orchestrate their scripts (`turbo run dev`, `turbo run test`) alongside the TS app —
same pattern as Rio's polyglot setup.

```
memory-layer/
├── apps/
│   ├── memory-api/                # Python (FastAPI) — core memory service
│   │   ├── src/
│   │   │   ├── main.py
│   │   │   ├── routers/
│   │   │   │   ├── memories.py
│   │   │   │   ├── auth.py        # Google OAuth verification, session JWT issuance
│   │   │   │   ├── keys.py        # API key create/revoke (session-JWT protected)
│   │   │   │   └── health.py
│   │   │   ├── middleware/
│   │   │   │   ├── auth.py        # API key hashing/validation, rate limiting
│   │   │   │   └── session.py     # session JWT validation (dashboard routes)
│   │   │   ├── services/
│   │   │   │   ├── extraction.py  # LLM pass: events -> candidate memories
│   │   │   │   ├── retrieval.py   # hybrid search
│   │   │   │   ├── scoring.py     # semantic + recency + importance
│   │   │   │   ├── dedup.py       # embedding-similarity dedup/consolidation
│   │   │   │   └── embedding.py   # in-process embedding model (read + write paths)
│   │   │   ├── db/
│   │   │   │   ├── models.py        # orgs, users, api_keys, memories, event_buffer
│   │   │   │   ├── session.py
│   │   │   │   └── migrations/      # Alembic
│   │   │   ├── schemas/
│   │   │   │   └── memory.py      # Pydantic models
│   │   │   └── config.py
│   │   ├── tests/
│   │   ├── pyproject.toml
│   │   └── package.json           # turbo task wrapper only
│   │
│   ├── mcp-server/                # Python (MCP SDK) — protocol adapter
│   │   ├── src/
│   │   │   ├── server.py
│   │   │   ├── tools/
│   │   │   │   ├── remember.py
│   │   │   │   ├── recall.py
│   │   │   │   ├── update.py
│   │   │   │   └── forget.py
│   │   │   └── client.py          # thin HTTP client -> memory-api
│   │   ├── tests/
│   │   ├── pyproject.toml
│   │   └── package.json           # turbo task wrapper only
│   │
│   └── web/                       # TypeScript (Next.js) — dashboard + landing page
│       ├── app/
│       │   ├── (marketing)/
│       │   │   └── page.tsx       # landing page
│       │   ├── (auth)/
│       │   │   └── login/         # Google OAuth sign-in page
│       │   ├── dashboard/
│       │   │   ├── memories/
│       │   │   ├── keys/          # API key management (create/revoke)
│       │   │   └── settings/
│       │   └── api/
│       ├── components/
│       ├── lib/
│       │   └── auth.ts            # Auth.js Google provider config
│       └── package.json
│
├── packages/
│   ├── shared-types/               # TS types mirroring API schemas (used by web)
│   └── config/                     # shared ruff / eslint / tsconfig configs
│
├── infra/
│   ├── docker-compose.yml          # postgres+pgvector — local dev
│   └── seed/                       # seed data for local testing
│
├── spec/                           # this folder — backend/infra specs
│   ├── 00-plan.md
│   ├── 01-todolist.md
│   ├── 02-folder-structure.md
│   ├── 03-architecture.md
│   ├── 04-workflow-dataflow.md
│   ├── 05-auth.md
│   ├── 06-database.md
│   └── design/                     # separate spec set — see spec/design/06-folder-structure.md
│
├── turbo.json
├── package.json                    # root workspace definition
└── README.md
```

## Notes
- `memory-api` and `mcp-server` are separate deployable services — the MCP server
  is a thin adapter, never touches the DB directly.
- `mcp-server` is stateless and safe to run as multiple instances behind a load
  balancer — no session affinity required. Every tool call must carry `org_id`/
  `session_id`/auth explicitly (see `spec/03-architecture.md`).
- `shared-types` keeps the web dashboard's TS types in sync with the Python API's
  Pydantic schemas (generate or hand-sync for MVP; codegen is a fast-follow).
- No `packages/` code should own business logic — that stays in `memory-api`.
