# DolphinBench adapter

`MemoriaBenchAdapter` in `memoria_adapter.py` is the HTTP client the DolphinBench harness imports. This module does not import DolphinBench, and DolphinBench is not vendored in this repo.

The harness file `my_harness.py` (created by `python -m harness.runner init` inside a clone of `mem0ai/dolphinbench`) imports this adapter. Add `evals/dolphinbench` to `PYTHONPATH` from the Memoria repo so that import resolves.

Construct the adapter with the bench `org_id`. A missing org id is rejected. Every request sends that `org_id` plus the persona `user_id`. Use `MEMORY_API_URL` and `MEMORY_API_KEY` for the Memory API (or pass `base_url`, `api_key`, and an `httpx.Client`).

`ingest` posts one `event_type=message` event, then polls `GET /events/pending?session_id=` until the count is 0. It sleeps briefly between polls and raises `RuntimeError` if the session is still pending when the wait expires. `reset` deletes that persona's memories, KV facts, and graph edges and nodes in the bench org. `freeze` sets a process flag; a later `ingest` for that persona raises `RuntimeError`.

## Clone

```bash
git clone https://github.com/mem0ai/dolphinbench.git ../dolphinbench
cd ../dolphinbench
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m harness.runner init
```

## Harness hooks

Fill in these three hooks in `my_harness.py`:

- ingest calls `adapter.ingest`
- each test calls `adapter.context` and must not receive fact cards
- memory writes during tests are rejected because `freeze` already ran
