# Memoria parity, observability, and DolphinBench

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the Mem0 and Supermemory gaps that change recall and context, instrument every read and write, then run Memoria on DolphinBench and record accuracy, cost, and latency.

**Architecture:** Six phases, each shippable on its own. Observability lands first so later phases have traces, metrics, and a token ledger. Retrieval and identity land before product surface. DolphinBench is last: it ingests three personas from empty memory, then grades 600 tool actions against read-only memory. Document connectors stay out.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Alembic, Postgres 16 + pgvector, pytest. New: `structlog`, OpenTelemetry SDK, `prometheus-client`. Eval harness: [mem0ai/dolphinbench](https://github.com/mem0ai/dolphinbench) (`python -m harness.runner`), not vendored into this repo.

## Global Constraints

- `org_id` stays mandatory on every query. A missing scope is a bug, not a default.
- Tests keep `MEMORIA_EMBEDDER=hash`. Any non-test process must refuse to start on `hash`.
- One org stores one embedding model. Search rejects rows stamped with a different `embedding_model`.
- Recall never calls an LLM. Entity and KV keys are written at ingest.
- Logs, traces, and metrics never contain memory text, prompts, API keys, or ciphertext.
- DolphinBench rules, copied from https://dolphinbench.ai/run/ : separate empty memory per persona; ingest every history message in order; each test is a fresh conversation with read-only memory; facts and expected answers stay outside the agent context; record every interaction, API usage, and all 600 results including failures.
- Submission ZIP contains only `ingestion.json` and `tests.json` at the root. Max 256 MiB.
- No Drive, Notion, Gmail, or document-chunk pipeline in this program.

---

## File map

| Path | Responsibility |
| --- | --- |
| `apps/memory-api/src/memory_api/observability/logging.py` | JSON logs, redaction, request context |
| `apps/memory-api/src/memory_api/observability/tracing.py` | Spans for embed, search stores, LLM, worker |
| `apps/memory-api/src/memory_api/observability/metrics.py` | Prometheus histograms and counters |
| `apps/memory-api/src/memory_api/observability/usage.py` | Token and latency ledger for cost |
| `apps/memory-api/src/memory_api/services/lexical.py` | Postgres FTS query and score |
| `apps/memory-api/src/memory_api/services/entities.py` | Normalize entity keys at write time |
| `apps/memory-api/src/memory_api/services/profile.py` | Static KV plus recent dynamic summary |
| `apps/memory-api/src/memory_api/routers/profile.py` | `GET /profile` |
| `apps/memory-api/src/memory_api/routers/feedback.py` | Useful / wrong signal |
| `apps/memory-api/src/memory_api/routers/webhooks.py` | Register and list webhook endpoints |
| `apps/memory-api/src/memory_api/services/webhooks.py` | Deliver `memory.written` events |
| `evals/dolphinbench/memoria_adapter.py` | Persona ingest, freeze, context for a test |
| `evals/dolphinbench/README.md` | Clone, smoke, full run, package |
| `infra/docker-compose.yml` | Optional OTLP collector |

Existing files that change: `config.py`, `main.py`, `embedding.py`, `hybrid_search.py`, `kv_candidates.py`, `graph_seeds.py`, `extraction.py`, `models.py`, `schemas/memory.py`, `routers/memories.py`, MCP `server.py`, Python and JS clients.

Next Alembic revision is `0008`. Later phases add `0009` through `0012`. Do not edit shipped revisions.

---

## Phase 0 — Observability

**Depends on:** nothing.

**Produces:** `configure_observability(app)`, span helper `start_span(name, **attrs)`, `record_llm_usage(...)`, `GET /metrics`.

Logs today are `logging.getLogger` lines such as `hybrid_search_timings` in `hybrid_search.py`. There is no trace id, no metrics endpoint, and no token ledger. DolphinBench’s cost number is impossible without the ledger.

### Task 1: Structured logs and request ids

**Files:**
- Create: `apps/memory-api/src/memory_api/observability/logging.py`
- Create: `apps/memory-api/tests/test_observability_logging.py`
- Modify: `apps/memory-api/src/memory_api/main.py`
- Modify: `apps/memory-api/pyproject.toml` (add `structlog>=24.4`)

**Interfaces:**
- Produces: `configure_logging() -> None`, `bind_request(request_id: str, org_id: str | None, route: str) -> None`, `clear_request() -> None`
- Log event keys, exact: `event`, `request_id`, `trace_id`, `org_id`, `route`, `status_code`, `duration_ms`, `level`

- [ ] **Step 1: Write the failing test**

```python
def test_log_drops_memory_text_and_secrets(capsys):
    configure_logging()
    log = structlog.get_logger()
    log.info(
        "search_done",
        content="user lives in Lisbon",
        api_key="mem_secret",
        duration_ms=12,
    )
    line = capsys.readouterr().out
    assert "Lisbon" not in line
    assert "mem_secret" not in line
    assert "duration_ms" in line
```

- [ ] **Step 2: Run** `cd apps/memory-api && uv run pytest tests/test_observability_logging.py::test_log_drops_memory_text_and_secrets -v`  
  Expected: FAIL, `configure_logging` missing.

- [ ] **Step 3: Implement** a structlog processor that deletes keys `content`, `prompt`, `api_key`, `authorization`, `ciphertext`, `kv_triples`, `graph_triples`. Middleware on `app` assigns `request_id` (honor incoming `X-Request-Id`, else uuid4), binds org id after auth, and logs one `request_finished` line.

- [ ] **Step 4: Re-run the test.** Expected: PASS.

- [ ] **Step 5: Commit** `feat: add redacted JSON request logs`

### Task 2: Traces around the hybrid read path

**Files:**
- Create: `apps/memory-api/src/memory_api/observability/tracing.py`
- Create: `apps/memory-api/tests/test_observability_tracing.py`
- Modify: `apps/memory-api/src/memory_api/services/hybrid_search.py`
- Modify: `apps/memory-api/src/memory_api/services/embedding.py`
- Modify: `apps/memory-api/src/memory_api/services/llm_json.py`
- Modify: `apps/memory-api/pyproject.toml` (`opentelemetry-api`, `opentelemetry-sdk`)

**Interfaces:**
- Produces: `start_span(name: str, **attributes: str) -> AbstractContextManager`
- Span names, exact: `embed`, `vector_search`, `kv_search`, `graph_search`, `llm_complete`, `worker_tick`
- Attributes allowed: `org_id`, `embedder`, `model`, `store`. No query text.

- [ ] **Step 1: Test** that `HybridRetriever.search` opens `embed` and `vector_search` spans. Use `InMemorySpanExporter`. Assert span names and that no span attribute contains the query string `"where does ava live"`.

- [ ] **Step 2: Run the test.** Expected: FAIL.

- [ ] **Step 3: Wrap** the existing timed blocks in `hybrid_search.py` (`_vector_search`, `_kv_search`, `_graph_search`) and `embed_text` / `complete_json`. Export OTLP only when `MEMORIA_OTEL_ENDPOINT` is set. Default exporter is the SDK’s no-op plus the in-memory exporter in tests.

- [ ] **Step 4: Re-run.** Expected: PASS.

- [ ] **Step 5: Commit** `feat: trace embed, search stores, and llm calls`

### Task 3: Metrics and usage ledger

**Files:**
- Create: `apps/memory-api/src/memory_api/observability/metrics.py`
- Create: `apps/memory-api/src/memory_api/observability/usage.py`
- Create: `apps/memory-api/alembic/versions/0008_usage_ledger.py`
- Create: `apps/memory-api/tests/test_usage_ledger.py`
- Modify: `apps/memory-api/src/memory_api/main.py` (`GET /metrics`)
- Modify: `apps/memory-api/src/memory_api/services/llm_json.py`
- Modify: `infra/docker-compose.yml` (optional `otel-collector` service, profile `obs`)

**Interfaces:**
- Produces: `record_llm_usage(*, org_id: UUID, user_id: str | None, model: str, input_tokens: int, output_tokens: int, duration_ms: float, trace_id: str | None) -> None`
- Table `llm_usage`: `id`, `org_id`, `user_id`, `model`, `input_tokens`, `output_tokens`, `duration_ms`, `trace_id`, `created_at`
- Metrics: `memoria_request_duration_seconds` histogram, `memoria_llm_tokens_total` counter labeled `direction` (`input`|`output`) and `model`

- [ ] **Step 1: Test** `record_llm_usage` inserts one row and `GET /metrics` returns the counter. Provider responses that omit usage store zeros, not a guess.

- [ ] **Step 2: Run.** Expected: FAIL.

- [ ] **Step 3: Implement** the table, the insert, and Prometheus text on `/metrics`. Parse `usage.prompt_tokens` and `usage.completion_tokens` from the existing chat completion JSON in `llm_json.py`.

- [ ] **Step 4: Run** `uv run pytest tests/test_usage_ledger.py tests/test_observability_tracing.py tests/test_observability_logging.py -v`  
  Expected: PASS.

- [ ] **Step 5: Commit** `feat: add metrics and llm usage ledger`

**Phase 0 done when:** a search log line has `request_id` and `duration_ms`, a trace has the span names above, `/metrics` scrapes, and a test proves content and keys are absent from logs.

---

## Phase 1 — Real embeddings

**Depends on:** Phase 0 (`embed` span already wraps `embed_text`).

**Produces:** `embedding_model` and `embedding_version` on `memories`. `get_embedder()` returns `MiniLMEmbedder` unless `MEMORIA_EMBEDDER=hash` and `MEMORIA_ENV=test`.

### Task 4: Refuse hash outside tests

**Files:**
- Modify: `apps/memory-api/src/memory_api/config.py` (add `env: str = "dev"`)
- Modify: `apps/memory-api/src/memory_api/services/embedding.py`
- Modify: `apps/memory-api/.env.example` (`MEMORIA_EMBEDDER=minilm`, `MEMORIA_ENV=dev`)
- Modify: `apps/memory-api/tests/conftest.py` or the existing settings fixture so tests set `MEMORIA_ENV=test`
- Test: `apps/memory-api/tests/test_embedder_config.py`

- [ ] **Step 1: Extend** `test_embedder_config.py` with `test_hash_embedder_rejected_outside_tests`. Call `get_embedder()` with `embedder="hash"` and `env="dev"`. Expect `RuntimeError` whose message contains `MEMORIA_EMBEDDER`.

- [ ] **Step 2: Run that test.** Expected: FAIL.

- [ ] **Step 3: Implement the guard** at the start of `get_embedder`. Leave `HashEmbedder` in place for `env=test`.

- [ ] **Step 4: Re-run** `uv run pytest tests/test_embedder_config.py -v`. Expected: PASS.

- [ ] **Step 5: Commit** `fix: reject hash embeddings outside tests`

### Task 5: Stamp and isolate embedding models

**Files:**
- Create: `apps/memory-api/alembic/versions/0009_embedding_stamp.py`
- Modify: `apps/memory-api/src/memory_api/db/models.py` (`Memory.embedding_model: str`, `Memory.embedding_version: int` default 1)
- Modify: `apps/memory-api/src/memory_api/services/dedup.py` and `db/repository.py` insert path
- Test: `apps/memory-api/tests/test_embedding_stamp.py`

**Interfaces:**
- `Embedder` gains `model_name: str` (`"hash"`, `"minilm"`, or the HF model id)
- `MemoryRepository.search` gains `embedding_model: str` and adds `WHERE embedding_model = :embedding_model`

- [ ] **Step 1: Test** inserting two memories with different `embedding_model` values and searching with `minilm` returns only the `minilm` row.

- [ ] **Step 2: Run.** Expected: FAIL.

- [ ] **Step 3: Migration** adds the columns, backfills existing rows to `hash` / version `1`, then sets both `NOT NULL`. Writes stamp `embedder.model_name`.

- [ ] **Step 4: Re-run.** Expected: PASS.

- [ ] **Step 5: Commit** `feat: stamp embedding model and filter search by it`

**Phase 1 done when:** dev refuses to boot on hash, and a mixed-model org cannot return hash vectors for a MiniLM query. Re-embedding old `hash` rows is a one-shot script in this phase: `python -m memory_api.cli reembed --from hash --to minilm`, updating `embedding` and `embedding_version`.

---

## Phase 2 — Lexical search, write-time entities

**Depends on:** Phase 1. Recall must stay correct after the embedder change.

**Produces:** `lexical_score` inside fusion. `derive_kv_candidates` and `derive_graph_seeds` lose their `api_key` argument.

### Task 6: Full-text score fused with vectors

**Files:**
- Create: `apps/memory-api/alembic/versions/0010_memory_fts.py`
- Create: `apps/memory-api/src/memory_api/services/lexical.py`
- Modify: `apps/memory-api/src/memory_api/services/hybrid_search.py`
- Modify: `apps/memory-api/src/memory_api/services/scoring.py`
- Test: `apps/memory-api/tests/test_lexical_search.py`

**Interfaces:**
- `lexical_search(session, *, org_id: UUID, q: str, session_id: str | None, limit: int) -> list[tuple[UUID, float]]`
- Generated column `memories.content_tsv tsvector` with `GIN` index, weighted from `content`
- `retrieval_score` stays the same weights. Relevance becomes `max(vector_similarity, lexical, kv_match, graph_score)`. `explain=true` adds `lexical` to `ScoreDetails`.

- [ ] **Step 1: Test** a memory `"billing entity is northwind"` is returned for query `"northwind"` even when the vector similarity is forced to `0` by a stub embedder that ignores text. Assert `score_details.lexical > 0` when `explain=true`.

- [ ] **Step 2: Run.** Expected: FAIL.

- [ ] **Step 3: Implement** `websearch_to_tsquery('english', q)` and `ts_rank_cd`. Normalize rank into 0–1 by dividing by the max rank in the candidate set (1.0 if the set is empty). Run this search in the same `ThreadPoolExecutor` as vector, KV, and graph. Add span `lexical_search`.

- [ ] **Step 4: Re-run.** Expected: PASS.

- [ ] **Step 5: Commit** `feat: fuse full-text rank into hybrid search`

### Task 7: Remove the LLM from recall

**Files:**
- Modify: `apps/memory-api/src/memory_api/services/kv_candidates.py`
- Modify: `apps/memory-api/src/memory_api/services/graph_seeds.py`
- Modify: `apps/memory-api/src/memory_api/services/hybrid_search.py` (stop passing `api_key` into search)
- Modify: `apps/memory-api/src/memory_api/routers/memories.py` (`search` no longer decrypts the org LLM key)
- Test: `apps/memory-api/tests/test_kv_candidates.py` and `tests/test_graph_seeds.py`

**Interfaces:**
- `derive_kv_candidates(query: str) -> list[tuple[str, str]]`
- `derive_graph_seeds(query: str) -> list[str]`
- Both are rules plus tokens only. Delete `_llm_candidates` and the graph equivalent.

- [ ] **Step 1: Test** `derive_kv_candidates("what language does the user prefer")` returns `("language", ...)` or `("preference", ...)` candidates and that the function signature rejects `api_key` (call with one argument).

- [ ] **Step 2: Run.** Expected: FAIL until the signature changes.

- [ ] **Step 3: Delete** the LLM branches. Keep the regex and token cap already in `kv_candidates.py` (`_CAP = 12`).

- [ ] **Step 4: Run** `uv run pytest tests/test_kv_candidates.py tests/test_graph_seeds.py tests/test_hybrid_benchmarks.py -q`. Expected: PASS, and no test patches an HTTP call on the search path.

- [ ] **Step 5: Commit** `fix: stop calling the llm during recall`

**Phase 2 done when:** `GET /memories/search` performs zero outbound HTTP calls. Extraction on `remember` and the worker may still call OpenRouter or Groq.

---

## Phase 3 — User and agent scope

**Depends on:** Phase 2. Filters apply to vector, FTS, KV, and graph.

**Produces:** `user_id: str | None` and `agent_id: str | None` on memories, KV facts, and graph nodes. Search and list accept both.

### Task 8: Columns and query filters

**Files:**
- Create: `apps/memory-api/alembic/versions/0011_scopes.py`
- Modify: `models.py`, `schemas/memory.py` (`MemoryCreate`, `MemorySearch` query params), `repository.py`, `stores/kv.py`, `stores/graph.py`, `routers/memories.py`
- Modify: `apps/mcp-server/src/mcp_server/server.py` and `packages/memoria-cloud-sdk/src/memoria_cloud/client.py`
- Test: `apps/memory-api/tests/test_scope_filters.py`

**Interfaces:**
- `POST /memories` body gains optional `user_id` and `agent_id` (strings, max 128, trimmed)
- `GET /memories/search` query gains the same. Omitted means “all users in the org”. Passed means `user_id` must match, and `agent_id` must match when provided.
- KV uniqueness becomes `(org_id, user_id, fact_type, entity)` with `user_id` stored as `''` when null so the unique constraint holds. `COALESCE` in the migration, not three partial indexes.

- [ ] **Step 1: Test** org A user `ava` cannot see user `sam`’s memory when `user_id=ava` is set, and can see it when `user_id` is omitted. Same for a graph edge and a KV fact.

- [ ] **Step 2: Run.** Expected: FAIL.

- [ ] **Step 3: Thread** the two ids through insert, fan-out, and all three searches. MCP `remember`, `recall`, and `emit` gain optional `user_id` and `agent_id`. Do not require them. Existing callers keep working.

- [ ] **Step 4: Re-run** `uv run pytest tests/test_scope_filters.py tests/test_tenant_query_layer.py -v`. Expected: PASS.

- [ ] **Step 5: Commit** `feat: filter memories by user and agent`

**Phase 3 done when:** two end users in one org get disjoint recall if the caller passes `user_id`, and DolphinBench can use one `user_id` per persona (`morgan`, `alex`, `riley`).

---

## Phase 4 — Profile, extraction policy, entity history

**Depends on:** Phase 3. Profile is scoped by `user_id`.

### Task 9: Profile endpoint

**Files:**
- Create: `apps/memory-api/src/memory_api/services/profile.py`
- Create: `apps/memory-api/src/memory_api/routers/profile.py`
- Modify: `main.py`, MCP `server.py` (tool `profile`)
- Test: `apps/memory-api/tests/test_profile.py`

**Interfaces:**
- `build_profile(*, org_id: UUID, user_id: str, token_budget: int = 800) -> Profile`
- `Profile`: `static: list[ProfileFact]`, `dynamic: list[str]`, `text: str`
- `ProfileFact`: `fact_type: str`, `entity: str`, `value: str | None`
- `GET /profile?user_id=&token_budget=`
- Static facts are current KV rows for that user, highest importance first.
- Dynamic lines are the 5 newest memories with `importance >= 0.6`, excluding any whose content duplicates a static fact value.
- `text` is `static` lines then `dynamic` lines, truncated with the existing `truncate_to_token_budget`.

- [ ] **Step 1: Test** a KV row `("city", "ava", "lisbon")` appears in `static`, and a semantic memory `"Ava moved to Lisbon"` is omitted from `dynamic` when the value `lisbon` is already in static. A second memory `"Prefers morning standups"` remains.

- [ ] **Step 2: Run.** Expected: FAIL.

- [ ] **Step 3: Implement** the builder and route. Register the router in `main.py`.

- [ ] **Step 4: Re-run.** Expected: PASS.

- [ ] **Step 5: Commit** `feat: add scoped profile context`

### Task 10: Per-org extraction instructions and categories

**Files:**
- Create: `apps/memory-api/alembic/versions/0012_extraction_policy.py`
- Modify: `models.py` (`Org.extraction_instructions: str | None`, `Org.categories: list[str]` JSONB default `[]`)
- Modify: `extraction.py` (`LlmExtractor` takes `instructions: str | None`, `categories: list[str]`)
- Modify: dashboard settings actions only if a settings form already exists for OpenRouter keys (`apps/web/components/features/dashboard/actions.ts`). If no settings page can hold a textarea, expose `PUT /org/extraction-policy` and stop.
- Test: `apps/memory-api/tests/test_extraction.py`

**Interfaces:**
- Candidate gains `categories: list[str]`
- Prompt appendix, exact shape: the org instructions string, then `Categories: a, b, c`, then `Assign zero or more of these categories. Do not invent categories.`
- Empty instructions keep today’s `_LLM_SYSTEM` unchanged.

- [ ] **Step 1: Test** with a fake provider that the user message sent to the model contains the instruction `"Ignore calendar small talk"` and the category `"shipping"`, and that a returned category `"not-allowed"` is dropped.

- [ ] **Step 2: Run.** Expected: FAIL.

- [ ] **Step 3: Implement** prompt assembly and category filtering against the org list.

- [ ] **Step 4: Re-run** `uv run pytest tests/test_extraction.py -v`. Expected: PASS.

- [ ] **Step 5: Commit** `feat: add per-org extraction instructions`

### Task 11: Normalize entities and keep KV history

**Files:**
- Create: `apps/memory-api/src/memory_api/services/entities.py`
- Create: `apps/memory-api/alembic/versions/0013_kv_history.py`
- Modify: `stores/kv.py`, `services/kv_fanout.py`, `stores/graph.py`
- Test: `apps/memory-api/tests/test_entity_normalize.py`

**Interfaces:**
- `normalize_entity(value: str) -> str` : NFKC, lowercase, collapse whitespace, strip punctuation except internal hyphens.
- `kv_fact_history` columns: `id`, `org_id`, `user_id`, `fact_type`, `entity`, `value`, `memory_id`, `valid_from`, `valid_to`
- On KV upsert, if value changes, close the open history row (`valid_to = now()`) and insert a new open row. Same rule as graph soft-invalidation.

- [ ] **Step 1: Test** `normalize_entity("  Berlin! ") == "berlin"` and a second put of `("city", "berlin", "lisbon")` leaves one current KV row whose value is `lisbon` and one history row for `berlin` with `valid_to` set.

- [ ] **Step 2: Run.** Expected: FAIL.

- [ ] **Step 3: Implement** and call `normalize_entity` on every KV entity and every graph subject and object before insert.

- [ ] **Step 4: Re-run.** Expected: PASS.

- [ ] **Step 5: Commit** `feat: normalize entities and version kv facts`

**Phase 4 done when:** `GET /profile?user_id=morgan` returns current facts without a search, and a city change keeps the previous value in history.

---

## Phase 5 — Ranking extras, dreaming, feedback, webhooks, filters

**Depends on:** Phase 4. Each task is independent of the others inside this phase and can ship alone.

### Task 12: Optional rerank

**Files:**
- Create: `apps/memory-api/src/memory_api/services/rerank.py`
- Modify: `hybrid_search.py`, `schemas/memory.py`, `routers/memories.py`
- Test: `apps/memory-api/tests/test_rerank.py`

**Interfaces:**
- `rerank(query: str, hits: list[RankedHit], *, limit: int) -> list[RankedHit]`
- Query flag `rerank=false` by default.
- Implementation is a local cross-encoder only when `MEMORIA_RERANKER=minilm` and the `minilm` extra is installed (`cross-encoder/ms-marco-MiniLM-L-6-v2`). Otherwise `rerank=true` returns 400 with `detail="reranker is not configured"`.
- Apply after fusion, before token-budget truncation. Span name `rerank`.

- [ ] **Step 1: Test** the unconfigured flag returns 400, and a stub `rerank` that reverses hits is what search returns when the flag is on.

- [ ] **Step 2–4: Fail, implement, pass.**

- [ ] **Step 5: Commit** `feat: add optional search rerank`

### Task 13: Dreaming batches

**Files:**
- Modify: `apps/memory-api/src/memory_api/worker.py`
- Modify: `apps/memory-api/src/memory_api/services/worker.py`
- Test: `apps/memory-api/tests/test_worker.py`

**Interfaces:**
- Setting `extract_group_window_seconds: int = 120`
- The worker groups pending events by `(org_id, session_id)` and waits until the newest event in the group is older than the window, or the group reaches `extract_batch_size`, or an event has `event_type=session_end`.
- One LLM extract call per group, not per event.

- [ ] **Step 1: Test** two message events 1 second apart in one session produce a single extractor call after the window is set to `0` in the test (so the test does not sleep). A `session_end` flushes immediately even when the window is `120`.

- [ ] **Step 2–4: Fail, implement, pass.**

- [ ] **Step 5: Commit** `feat: extract memories from session batches`

### Task 14: Feedback, metadata filters, webhooks

**Files:**
- Create: `apps/memory-api/alembic/versions/0014_feedback_webhooks.py`
- Create: `routers/feedback.py`, `routers/webhooks.py`, `services/webhooks.py`
- Modify: `repository.py` list/search filter on `source_metadata`
- Test: `tests/test_feedback.py`, `tests/test_metadata_filter.py`, `tests/test_webhooks.py`

**Interfaces:**
- `POST /memories/{id}/feedback` body `{ "useful": true|false }`. `useful=true` adds `0.1` to importance, cap `1.0`. `useful=false` subtracts `0.2`, floor `0.0`. One vote per `(memory_id, api_key_id)` stored in `memory_feedback`.
- Search query `metadata` is a JSON object. Match is containment: `source_metadata @> :metadata`.
- `POST /webhooks` body `{ "url": "https://...", "events": ["memory.written"] }`. Secret is returned once. Delivery is a POST with header `X-Memoria-Signature` HMAC-SHA256 of the raw body. Payload: `{ "event", "memory_id", "org_id", "user_id" }`. No memory content. Failures are logged and do not fail `remember`.

- [ ] **Step 1: Three tests.** Feedback clamps at 1.0. `metadata={"source":"dolphin"}` does not return a memory tagged `cursor`. A webhook receiver records the signature and the writer still returns 201 when the receiver returns 500.

- [ ] **Step 2–4: Fail, implement, pass.**

- [ ] **Step 5: Commit** `feat: add feedback, metadata filters, and webhooks`

**Phase 5 done when:** those three tests pass. Rerank stays off in DolphinBench unless a smoke run shows a gain worth the latency.

---

## Phase 6 — DolphinBench

**Depends on:** Phases 0–4. Phase 5 is optional for the first submission.

Dataset, from https://dolphinbench.ai/dataset/ : Morgan Chen 3,400 messages / 200 tests, Alex Valdez 5,011 / 200, Riley Tanaka 5,128 / 200. Histories are years long. Ingestion and evaluation spend model money. Do not run the full set until the smoke gate passes.

### Task 15: Adapter

**Files:**
- Create: `evals/dolphinbench/memoria_adapter.py`
- Create: `evals/dolphinbench/test_adapter.py`
- Create: `evals/dolphinbench/README.md`

**Interfaces:**
- `class MemoriaBenchAdapter`
  - `reset(persona: str) -> None` deletes that persona’s `user_id` memories in the bench org
  - `ingest(persona: str, session_id: str, content: str) -> None` calls `POST /events` with `event_type=message` and `user_id=persona`, then waits until the worker has drained that session
  - `freeze(persona: str) -> None` sets a process flag the adapter checks; further `ingest` raises `RuntimeError`
  - `context(persona: str, request: str, token_budget: int = 2048) -> str` concatenates `GET /profile?user_id=persona` text and `GET /memories/search?user_id=persona&q=request` contents, profile first
- The adapter does not import DolphinBench. The harness file `my_harness.py` (created by `python -m harness.runner init` inside a clone of `mem0ai/dolphinbench`) imports this adapter.

- [ ] **Step 1: Test** with `httpx.MockTransport` that `ingest` posts one event, `freeze` then `ingest` raises, and `context` places profile text before search hits.

- [ ] **Step 2–4: Fail, implement, pass.** Unit tests only. No network.

- [ ] **Step 3b: README commands**, exact:

```bash
git clone https://github.com/mem0ai/dolphinbench.git ../dolphinbench
cd ../dolphinbench
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m harness.runner init
```

Document the three harness hooks to fill in: ingest calls `adapter.ingest`, each test calls `adapter.context` and must not receive fact cards, and memory writes during tests are rejected because `freeze` already ran.

- [ ] **Step 5: Commit** `feat: add dolphinbench memoria adapter`

### Task 16: Smoke gate, then the paid run

**Files:**
- Create: `evals/dolphinbench/smoke.sh`
- Modify: `evals/dolphinbench/README.md`

Smoke is not a DolphinBench score. It checks the adapter against a local Memory API.

- [ ] **Step 1: `smoke.sh`** starts nothing itself. It requires `MEMORY_API_URL` and `MEMORY_API_KEY`. It ingests 20 fixture lines (checked into `evals/dolphinbench/fixtures/morgan-sample.jsonl`), calls `freeze`, then `context` for a query that matches a fixture fact. Exit 0 only if the fact string is in the context and `GET /metrics` shows `memoria_llm_tokens_total` or the usage ledger has rows for that `user_id`.

- [ ] **Step 2: Run smoke** against the local compose stack with `MEMORIA_EMBEDDER=minilm` and `MEMORIA_ENV=dev`. Expected: exit 0.

- [ ] **Step 3: Full run**, only after smoke exits 0, from the DolphinBench clone:

```bash
python -m harness.runner prepare
python -m harness.runner ingest --confirm-paid-calls
python -m harness.runner evaluate --confirm-paid-calls
python -m harness.runner package
```

- [ ] **Step 4: Record** in `evals/dolphinbench/RESULTS.md` (gitignored if it contains raw transcripts; commit only the summary table): accuracy, total cost, median task latency, model id, harness name, Memoria git SHA, and the path of `tmp/my-agent/submission.zip`. Do not commit the ZIP.

- [ ] **Step 5: Commit** `docs: record dolphinbench smoke gate` (the script and README only, not the paid-run transcripts).

**Phase 6 done when:** smoke passes, and a full run has produced `ingestion.json` plus `tests.json` covering personas `morgan`, `alex`, and `riley` and 600 tests. Uploading the ZIP to https://dolphinbench.ai/run/ is a manual step.

---

## Order

```text
Phase 0 observability
    -> Phase 1 embeddings
        -> Phase 2 lexical search + no LLM on read
            -> Phase 3 user_id / agent_id
                -> Phase 4 profile + extraction policy + KV history
                    -> Phase 5 rerank, dreaming, feedback, webhooks, filters
                        -> Phase 6 DolphinBench smoke, then paid 600
```

Phase 5 tasks do not block Phase 6. Run Phase 6 as soon as Phase 4 is green if the goal is a first leaderboard point.

## Out of scope

- Connectors and document chunking
- A second graph database
- Learned fusion weights
- Re-running DolphinBench on every pull request

## Self-review

- Spec coverage: embedder default, FTS, LLM off the read path, user/agent scope, profile, custom instructions, entity history, rerank, dreaming, feedback, webhooks, metadata filters, traces, metrics, usage ledger, DolphinBench smoke and full run. Each has a task.
- Document ingest is named as out of scope on purpose.
- Signatures used later (`record_llm_usage`, `normalize_entity`, `build_profile`, `MemoriaBenchAdapter.context`) match the task that defines them.
