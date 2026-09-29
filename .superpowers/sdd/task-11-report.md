# Task 11 report: Normalize entities and keep KV history

Status: DONE

Commit: see the commit created with subject `feat: normalize entities and version kv facts`

## What landed

`normalize_entity` applies NFKC, lowercase, collapsed whitespace, and strips punctuation except hyphens that sit between alphanumeric characters. `normalize_entity("  Berlin! ")` is `berlin`. `well-known!` stays `well-known`.

KV puts and KV fan-out normalize the entity before insert. Graph subject and object keys (and node keys, including lookup) use the same function. Relation tokens stay on strip-and-lowercase.

A changed KV value closes the open `kv_fact_history` row (`valid_to = now()`) and inserts a new open row, matching graph soft-invalidation. The current `kv_facts` row is still a single upsert. A second put of `("city", "berlin", "lisbon")` leaves one current row whose value is `lisbon` and a history row for `berlin` with `valid_to` set. History `user_id` is the stored scope id, `''` when the caller passed null, so the fact and its history share a scope.

The profile endpoint was not changed.

## TDD evidence

### RED

Command (from `apps/memory-api`), before `entities.py` or history existed:

```bash
uv run pytest tests/test_entity_normalize.py -v --tb=short
```

Result: collection error, feature missing.

```
ERROR tests/test_entity_normalize.py
ImportError while importing test module '.../tests/test_entity_normalize.py'.
tests/test_entity_normalize.py:10: in <module>
    from memory_api.services.entities import normalize_entity
E   ModuleNotFoundError: No module named 'memory_api.services.entities'
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
=============================== 1 error in 0.29s ===============================
```

### GREEN

Command:

```bash
uv run pytest tests/test_entity_normalize.py -v --tb=short
```

Result: 5 passed in 0.27s.

- `test_kv_fact_history_columns`
- `test_normalize_entity_strips_punctuation_and_keeps_internal_hyphens`
- `test_second_kv_put_keeps_previous_value_in_history`
- `test_kv_and_graph_normalize_entities_before_insert`
- `test_kv_fanout_normalizes_entity_before_put`

Full memory-api suite, after `uv run alembic upgrade head` (`0012_extraction_policy -> 0013_kv_history`):

```bash
uv run pytest -q --tb=line
```

Result: 201 passed, 1 warning (pre-existing Starlette/`httpx` deprecation).

## Files changed

- `apps/memory-api/src/memory_api/services/entities.py` (new)
- `apps/memory-api/alembic/versions/0013_kv_history.py` (new; `revision = "0013_kv_history"`, `down_revision = "0012_extraction_policy"`)
- `apps/memory-api/src/memory_api/db/models.py` (`KvFactHistory`)
- `apps/memory-api/src/memory_api/stores/kv.py`
- `apps/memory-api/src/memory_api/services/kv_fanout.py`
- `apps/memory-api/src/memory_api/stores/graph.py`
- `apps/memory-api/src/memory_api/stores/types.py` (`KVFactHistory`)
- `apps/memory-api/src/memory_api/stores/protocols.py`
- `apps/memory-api/src/memory_api/stores/noop.py`
- `apps/memory-api/tests/test_entity_normalize.py` (new)

## Self-review

- History is written only after the memory row is confirmed in the same org. A rejected put does not open a history row.
- On a value change, open history rows are flushed closed before the new open row is inserted, so the partial unique index `uq_kv_fact_history_open` can hold.
- An unchanged value still updates the current fact and does not append history.
- Null `user_id` is stored as `''` on both the fact and the history row.
- Every history query includes `org_id`.
- Graph relations are not run through `normalize_entity`. Subject, object, and node keys are.
- No new logs of memory text, prompts, or keys. Recall still does not call an LLM. `MEMORIA_EMBEDDER=hash` is unchanged.
- Profile, rerank, dreaming, feedback, and webhooks were not added.
