# Phase 3 — Intelligence

Approved design for automatic memory creation. Explicit `remember` stays.

## Write paths

| Path | When | Hot path? |
|---|---|---|
| `POST /memories` / MCP `remember` | Human or agent decides this is a memory | Sync insert (with dedup) |
| `POST /events` / MCP `emit` | Raw session signal | Sync enqueue only |
| Extraction worker | Batched off the harness loop | Async extract → dedup → insert |

`recall` does not care how a row was created. Dedup treats manual and extracted memories as one pool.

## Ingest

`POST /events` (API key). Body: `session_id`, `event_type` (`message` | `tool_call` | `diff` | `session_end`), `payload` (object).

Enqueue is **filtered**. Noisy `tool_call` names (`read_file`, `grep`, `glob`, `list_dir`, `ls`, `search_files`, `read`) are skipped unless `payload.important` is true. `session_end` always enqueues.

- skipped → `200` `{ "status": "skipped" }` (no row)
- queued → `202` `{ "status": "queued", "id": ... }`

MCP `emit` is a thin adapter with the same identity args as `remember` (`org_id`, `session_id`, `api_key`).

## Worker

In-process: `uv run python -m memory_api.worker`. Polls `event_buffer` (`status`, `created_at`). Claims `pending` → `processing` when pending count for a session ≥ `MEMORIA_EXTRACT_BATCH_SIZE` (default 10) **or** a `session_end` event is present. Failed batches → `failed`; success → `processed`.

Does not run inside `POST /events`.

## Extractor

`MEMORIA_EXTRACTOR=heuristic|llm` (default `heuristic`). Interface: events → list of candidates `{content, memory_type, importance, source_metadata}`. **Empty list is success.**

Heuristic (MVP): durable language in `payload.content` / `payload.text` / `payload.summary` (prefer / always / never / we use / decided / fixed / workaround). LLM is the same interface; not required for tests.

## Dedup and consolidation

Before insert (explicit `remember` and extracted candidates): embed, nearest-neighbor in org (optional session). Cosine similarity ≥ `MEMORIA_DEDUP_THRESHOLD` (default 0.92) → do **not** insert; bump `importance` (cap 1.0) and `access_count` on the existing row.

Nearest-neighbor lookup must **not** increment `access_count` (unlike recall `search`).

Consolidation is a separate pass: same session, similarity ≥ `MEMORIA_CONSOLIDATE_THRESHOLD` (default 0.85), keep the richer/higher-importance row, delete the other.

## Dashboard

Session-JWT `GET /memories?session_id=&memory_type=&q=`. List/filter only. No overview stats, settings, or manual review in this slice. Browsing does not count as recall (`access_count` unchanged).
