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
import math
import os
import re
import sys
import uuid

import httpx
from memoria_adapter import MemoriaBenchAdapter

BENCH_ORG = "11111111-1111-1111-1111-111111111111"
PERSONA = "morgan"
EXPECTED_LINES = 20
_TOKEN_SAMPLE = re.compile(r"^memoria_llm_tokens_total(?:\{.*\})?\s+(\S+)")


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


def token_counter_is_positive(body: str) -> bool:
    """True only when a memoria_llm_tokens_total sample value is greater than 0."""
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _TOKEN_SAMPLE.match(stripped)
        if match is None:
            continue
        try:
            value = float(match.group(1))
        except ValueError:
            continue
        if math.isfinite(value) and value > 0:
            return True
    return False


def fetch_metrics(base_url: str) -> str | None:
    try:
        response = httpx.get(f"{base_url.rstrip('/')}/metrics", timeout=30.0)
        response.raise_for_status()
    except Exception:
        return None
    return response.text


class LedgerQueryError(Exception):
    pass


def database_url() -> str:
    return (
        os.environ.get("MEMORIA_DATABASE_URL") or os.environ.get("DATABASE_URL") or ""
    ).strip()


def ledger_count(org_id: str, user_id: str) -> int:
    """Count llm_usage rows for this org and user. Raises LedgerQueryError on failure."""
    raw = database_url()
    if not raw:
        raise LedgerQueryError("usage ledger is not configured")
    try:
        org_uuid = uuid.UUID(org_id)
    except ValueError as exc:
        raise LedgerQueryError("org_id is not a UUID") from exc
    dsn = raw.replace("postgresql+psycopg://", "postgresql://", 1).replace(
        "postgresql+psycopg2://", "postgresql://", 1
    )
    try:
        import psycopg
    except ImportError as exc:
        raise LedgerQueryError("usage ledger driver is missing") from exc
    try:
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM llm_usage WHERE org_id = %s AND user_id = %s",
                    (org_uuid, user_id),
                )
                row = cur.fetchone()
    except LedgerQueryError:
        raise
    except Exception as exc:
        raise LedgerQueryError("usage ledger query failed") from exc
    if row is None or row[0] is None:
        raise LedgerQueryError("usage ledger query failed")
    return int(row[0])


def main() -> None:
    rows, fact, query = load_fixture(sys.argv[1])
    org_id = os.environ.get("MEMORY_ORG_ID", BENCH_ORG).strip() or BENCH_ORG
    before: int | None = None
    if database_url():
        try:
            before = ledger_count(org_id, PERSONA)
        except LedgerQueryError:
            fail("usage ledger query failed")
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
    metrics = fetch_metrics(adapter.base_url)
    if metrics is not None and token_counter_is_positive(metrics):
        print("smoke ok")
        return
    if before is None:
        fail(
            "memoria_llm_tokens_total sample is not greater than 0"
            " and usage ledger is not configured"
        )
    try:
        after = ledger_count(org_id, PERSONA)
    except LedgerQueryError:
        fail("usage ledger query failed")
    if after > before:
        print("smoke ok")
        return
    fail(
        "memoria_llm_tokens_total sample is not greater than 0"
        " and this run added no usage-ledger row for org_id and user_id"
    )


if __name__ == "__main__":
    main()
PY
