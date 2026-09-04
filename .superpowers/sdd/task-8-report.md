# Task 8 Report: Union search and explain

## Status
**Complete**

## What was done
- Kept vector retrieval first, then optionally derived and searched exact KV candidates.
- Loaded an organization's encrypted OpenRouter key/model only for session-backed repositories; in-memory repositories use the rules path.
- Unioned vector and KV results by memory ID, skipped missing memories, and degraded to vector-only results when KV search raises.
- Scored relevance as `max(vector_similarity, kv_match or 0)` and exposed accurate vector/KV explain sources.
- Preserved Phase 0 vector-only explain behavior when no KV match contributes.

## Files
- Modified `apps/memory-api/src/memory_api/routers/memories.py`.
- Modified `apps/memory-api/tests/test_memories_api.py`.

## TDD evidence
- RED: `test_search_unions_kv_hit_when_vector_is_weak` failed because `kv_match` was `None`.
- GREEN: the focused test passed after the union implementation.
- API tests: **14 passed**.
- Full memory API suite: **94 passed, 5 skipped**.
- Ruff: all checks passed for changed Python files.

## Commit
`Union KV exact matches into memory search scoring.`

## Concerns
- The full suite reports one existing Starlette `TestClient` deprecation warning.
