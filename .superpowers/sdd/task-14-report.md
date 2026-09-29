# Task 14 report: Feedback, metadata filters, webhooks

Status: DONE

Commit: `feat: add feedback, metadata filters, and webhooks`

## What landed

`POST /memories/{id}/feedback` takes `{ "useful": true|false }`. `useful=true` adds `0.1` to importance, capped at `1.0`. `useful=false` subtracts `0.2`, floored at `0.0`. One vote per `(memory_id, api_key_id)` is stored in `memory_feedback`. A second vote from the same key returns 409 and leaves importance unchanged. The vote and the memory lookup are scoped to the caller's `org_id`.

Search and list accept a `metadata` query value that is a JSON object. The match is containment: `source_metadata @> :metadata`. `metadata={"source":"dolphin"}` does not return a memory tagged `cursor`. The same predicate is applied to vector hits and to lexical, KV, and graph hits that are merged into hybrid search. `org_id` and `embedding_model` stay on the search statement.

`POST /webhooks` takes `{ "url", "events" }` and returns the signing secret once. `GET /webhooks` lists endpoints for the caller's org and does not include the secret. On a new memory, delivery is a POST whose body is exactly `{ "event", "memory_id", "org_id", "user_id" }` and whose `X-Memoria-Signature` header is HMAC-SHA256 of those raw bytes. A receiver that returns 500 is logged with `org_id`, webhook id, and the exception type. The log line does not include memory text, prompts, API keys, or ciphertext, and `remember` still returns 201. The lookup runs inside a savepoint so a failed query cannot abort the writer's transaction.

Migration `0014_feedback_webhooks` revises `0013_kv_history`. It creates `memory_feedback` (unique on `memory_id`, `api_key_id`) and `webhook_endpoints`.

## TDD evidence

### RED

An uncommitted model edit had defined `MemoryFeedback` twice, so the first run could not collect tests (`InvalidRequestError: Table 'memory_feedback' is already defined`). The duplicate class was removed. The routes were still unwired and search did not filter `source_metadata`. Re-run:

Command (from `apps/memory-api`):

```bash
uv run pytest tests/test_feedback.py tests/test_metadata_filter.py tests/test_webhooks.py -v --tb=line
```

Result: 6 failed. Failures were the missing behavior.

- `test_useful_feedback_clamps_importance_at_1_0`: `POST /memories/{id}/feedback` returned 404 (`assert 404 == 200`).
- `test_not_useful_feedback_floors_importance_at_0`: same 404.
- `test_second_vote_for_the_same_api_key_does_not_change_importance`: same 404.
- `test_feedback_without_api_key_is_rejected`: 404, so the missing route never reached auth (`assert 404 == 401`).
- `test_dolphin_metadata_does_not_return_a_memory_tagged_cursor`: search returned both the cursor memory and the dolphin memory.
- `test_webhook_receiver_records_signature_and_remember_returns_201_on_500`: `POST /webhooks` returned 404 (`assert 404 == 201`).

### GREEN

Command:

```bash
uv run pytest tests/test_feedback.py tests/test_metadata_filter.py tests/test_webhooks.py -v --tb=short
```

Result: 6 passed, 1 warning (pre-existing Starlette/`httpx` deprecation).

Full memory-api suite, after `uv run alembic upgrade head` (the first full run failed six existing Postgres tests because webhook lookup queried `webhook_endpoints` before that table existed and aborted the request transaction):

```bash
uv run pytest -q --tb=line
```

Result: 212 passed, 1 warning (same Starlette/`httpx` deprecation).

`uv run ruff check` on the touched Python files was clean.

## Files changed

- `apps/memory-api/alembic/versions/0014_feedback_webhooks.py` (new; `revision = "0014_feedback_webhooks"`, `down_revision = "0013_kv_history"`)
- `apps/memory-api/src/memory_api/routers/feedback.py` (new)
- `apps/memory-api/src/memory_api/routers/webhooks.py` (new)
- `apps/memory-api/src/memory_api/services/webhooks.py` (new)
- `apps/memory-api/src/memory_api/db/models.py` (`MemoryFeedback`, `WebhookEndpoint`)
- `apps/memory-api/src/memory_api/db/repository.py` (list/search containment filter)
- `apps/memory-api/src/memory_api/routers/memories.py` (metadata query param, deliver on insert)
- `apps/memory-api/src/memory_api/services/hybrid_search.py` (pass metadata through hybrid recall)
- `apps/memory-api/src/memory_api/services/worker.py` (deliver when extraction inserts a memory)
- `apps/memory-api/src/memory_api/stores/protocols.py`
- `apps/memory-api/src/memory_api/stores/vector.py`
- `apps/memory-api/src/memory_api/main.py` (mount the two routers)
- `apps/memory-api/tests/test_feedback.py` (new)
- `apps/memory-api/tests/test_metadata_filter.py` (new)
- `apps/memory-api/tests/test_webhooks.py` (new)

## Self-review

- Duplicate `MemoryFeedback` / `WebhookEndpoint` declarations were removed before the real RED run. SQLAlchemy cannot register the same table twice.
- Feedback is rejected without a bearer token (401) and a repeat vote does not move importance.
- Containment is `@>` on `source_metadata`, and a cursor-tagged memory stays out of a dolphin filter on both search and list.
- Webhook bodies have only `event`, `memory_id`, `org_id`, and `user_id`. The signing secret is absent from the list response.
- Delivery failures are logged without memory text. The Postgres lookup uses a savepoint so a failed `SELECT` does not roll back the memory insert. After `alembic upgrade head`, the six Postgres tests that had been emptied by that rollback passed.
- `org_id` remains required on feedback, webhook list, and the search statement. Recall still does not call an LLM.
