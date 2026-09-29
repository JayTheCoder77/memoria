#!/usr/bin/env bash
# Checks MemoriaBenchAdapter against a Memory API the caller already started.
# Does not start Docker, clone DolphinBench, or call the paid harness.
set -euo pipefail

if [[ -z "${MEMORY_API_URL:-}" || -z "${MEMORY_API_KEY:-}" ]]; then
  echo "smoke failed: MEMORY_API_URL and MEMORY_API_KEY are required" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FIXTURE="${ROOT}/fixtures/morgan-sample.jsonl"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:${PYTHONPATH}}"

python3 - "${FIXTURE}" <<'PY'
import json
import os
import sys

import httpx
from memoria_adapter import MemoriaBenchAdapter

BENCH_ORG = "11111111-1111-1111-1111-111111111111"
PERSONA = "morgan"
EXPECTED_LINES = 20


def fail(message: str) -> None:
    print(f"smoke failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_fixture(path: str) -> tuple[list[dict[str, str]], str, str]:
    try:
        raw = open(path, encoding="utf-8").read().splitlines()
    except OSError:
        fail("fixture is unreadable")
    rows: list[dict[str, str]] = []
    fact = ""
    query = ""
    for line in raw:
        if not line.strip():
            fail("fixture contains a blank line")
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            fail("fixture line is not JSON")
        if not isinstance(item, dict):
            fail("fixture line is not an object")
        persona = item.get("persona")
        session_id = item.get("session_id")
        content = item.get("content")
        if persona != PERSONA or not isinstance(session_id, str) or not session_id.strip():
            fail("fixture line is missing persona or session_id")
        if not isinstance(content, str) or not content.strip():
            fail("fixture line is missing content")
        rows.append(
            {
                "persona": persona,
                "session_id": session_id.strip(),
                "content": content,
            }
        )
        if item.get("smoke_fact") is True:
            if fact:
                fail("fixture has more than one smoke fact")
            smoke_query = item.get("smoke_query")
            if not isinstance(smoke_query, str) or not smoke_query.strip():
                fail("smoke fact is missing a query")
            fact = content
            query = smoke_query.strip()
    if len(rows) != EXPECTED_LINES:
        fail("fixture must contain 20 lines")
    if len({row["session_id"] for row in rows}) != EXPECTED_LINES:
        fail("fixture session ids are not unique")
    if not fact:
        fail("fixture is missing a smoke fact")
    return rows, fact, query


def metrics_show_tokens(base_url: str) -> bool:
    try:
        response = httpx.get(f"{base_url.rstrip('/')}/metrics", timeout=30.0)
        response.raise_for_status()
    except Exception:
        return False
    return "memoria_llm_tokens_total" in response.text


def ledger_has_user(user_id: str) -> bool:
    raw = (
        os.environ.get("MEMORIA_DATABASE_URL") or os.environ.get("DATABASE_URL") or ""
    ).strip()
    if not raw:
        return False
    dsn = raw.replace("postgresql+psycopg://", "postgresql://", 1).replace(
        "postgresql+psycopg2://", "postgresql://", 1
    )
    try:
        import psycopg
    except ImportError:
        return False
    try:
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM llm_usage WHERE user_id = %s LIMIT 1",
                    (user_id,),
                )
                return cur.fetchone() is not None
    except Exception:
        return False


def main() -> None:
    rows, fact, query = load_fixture(sys.argv[1])
    org_id = os.environ.get("MEMORY_ORG_ID", BENCH_ORG).strip() or BENCH_ORG
    adapter = MemoriaBenchAdapter(
        org_id=org_id,
        api_key=os.environ["MEMORY_API_KEY"],
        base_url=os.environ["MEMORY_API_URL"],
    )
    try:
        adapter.reset(PERSONA)
        for row in rows:
            adapter.ingest(row["persona"], row["session_id"], row["content"])
        adapter.freeze(PERSONA)
        context = adapter.context(PERSONA, query)
    except Exception:
        fail("adapter request failed")
    finally:
        adapter.close()
    if fact not in context:
        fail("fixture fact was not in context")
    if metrics_show_tokens(adapter.base_url) or ledger_has_user(PERSONA):
        print("smoke ok")
        return
    fail("memoria_llm_tokens_total missing and usage ledger has no rows for user_id")


if __name__ == "__main__":
    main()
PY
