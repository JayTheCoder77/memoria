# DolphinBench adapter

`MemoriaBenchAdapter` in `memoria_adapter.py` is the HTTP client the DolphinBench harness imports. This module does not import DolphinBench, and DolphinBench is not vendored in this repo.

The harness file `my_harness.py` (created by `python -m harness.runner init` inside a clone of `mem0ai/dolphinbench`) imports this adapter. Add `evals/dolphinbench` to `PYTHONPATH` from the Memoria repo so that import resolves.

Construct the adapter with the bench `org_id`. A missing org id is rejected. Every request sends that `org_id` plus the persona `user_id`. Use `MEMORY_API_URL` and `MEMORY_API_KEY` for the Memory API (or pass `base_url`, `api_key`, and an `httpx.Client`).

`ingest` posts one `event_type=message` event, then one `event_type=session_end` for the same persona and session so the worker flushes that group, then polls `GET /events/pending?session_id=` until the pending count is 0. It sleeps briefly between polls and raises `RuntimeError` if the failed count is greater than 0 or the session is still pending when the wait expires. `reset` deletes that persona's memories, KV facts, and graph edges and nodes in the bench org. `freeze` sets a process flag; a later `ingest` for that persona raises `RuntimeError`.

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

## Smoke

Smoke is not a DolphinBench score. It checks `MemoriaBenchAdapter` against a Memory API you already started. `evals/dolphinbench/smoke.sh` does not start Docker Compose, clone DolphinBench, or call the harness.

Start the API yourself with `MEMORIA_EMBEDDER=minilm` and `MEMORIA_ENV=dev`. Then, from this repo, with a Python that has `httpx` (the Memory API environment):

```bash
export MEMORY_API_URL=http://127.0.0.1:8000
export MEMORY_API_KEY=mem_your_key
uv run --project apps/memory-api ./evals/dolphinbench/smoke.sh
```

`MEMORY_API_URL` and `MEMORY_API_KEY` are required. Optional `MEMORY_ORG_ID` is the org id the adapter sends (default `11111111-1111-1111-1111-111111111111`); the API still authorizes with the key. The script reads the 20 JSONL lines in `evals/dolphinbench/fixtures/morgan-sample.jsonl`, resets persona `morgan`, ingests each line in order, calls `freeze`, then `context` with the `smoke_query` on the line marked `"smoke_fact": true`. It exits 0 only when that line's `content` is in the context, and either `GET /metrics` contains `memoria_llm_tokens_total` or the `llm_usage` table has a row whose `user_id` is `morgan`.

The ledger check runs only when the metrics text does not contain the counter name. It uses `MEMORIA_DATABASE_URL` or `DATABASE_URL` if one is set. The script does not print memory text, prompts, or the API key.

## Paid run

Run this only after `smoke.sh` exits 0, from the DolphinBench clone (not from this script):

```bash
python -m harness.runner prepare
python -m harness.runner ingest --confirm-paid-calls
python -m harness.runner evaluate --confirm-paid-calls
python -m harness.runner package
```

Record accuracy, total cost, median task latency, model id, harness name, Memoria git SHA, and the path of `tmp/my-agent/submission.zip` in `evals/dolphinbench/RESULTS.md`. Do not commit the ZIP. Do not commit `RESULTS.md` when it contains raw transcripts.
