# Phase 5 — Hardening & operations

Shipped after entity-overlap dedup. Read-only ops surfaces plus consolidate
integrity. Caps, confidence floor, hybrid search, and explain timings already
exist.

## List APIs

Org-scoped machine-key auth, same as `/memories`.

- `GET /kv-facts?limit=&offset=` — `{fact_type, entity, value, memory_id, updated_at}`. Cap 100.
- `GET /graph-edges?valid_only=true&limit=&offset=` — `{subject, relation, object, valid, valid_from, valid_to, confidence, memory_id}`.

## Dashboard

New sidebar pages **Facts** (`/dashboard/facts`) and **Graph** (`/dashboard/graph`). Read-only tables in the existing dashboard language. No edits.

## Consolidate / forget

`consolidate_session`: after deleting the loser, `UPDATE graph_edges SET memory_id = winner.id WHERE memory_id = loser.id`. KV remains `ON DELETE CASCADE`.

`forget`: unchanged. KV rows cascade-delete; graph `memory_id` becomes null (`ON DELETE SET NULL`).

## Temporal

MCP `recall` accepts optional `as_of` and forwards it to `GET /memories/search`. HTTP already supports the param.

## Docs

Hybrid architecture, fusion-weight tuning, and failure modes (KV/graph write isolation, regex fallback, confidence floor, disabled stores) in `spec/03-architecture.md` plus a short README pointer. Existing pytest query-class tests remain the quality suite.

## Non-goals

- Re-embed job / `embedding_version` column
- Hard `fact_type` allow-list
- Load-test harness
- Graph FK change to CASCADE
