"""Measure p50/p95 latency for GET /memories/search."""

from __future__ import annotations

import argparse
import statistics
import time

import httpx


def percentiles(samples: list[float]) -> tuple[float, float]:
    ordered = sorted(samples)
    def at(pct: float) -> float:
        index = min(int(len(ordered) * pct), len(ordered) - 1)
        return ordered[index]

    return at(0.50), at(0.95)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--session-id", default="bench")
    parser.add_argument("--q", default="recall latency")
    parser.add_argument("--n", type=int, default=50)
    args = parser.parse_args()
    samples: list[float] = []
    with httpx.Client(base_url=args.base_url, timeout=10.0) as client:
        for _ in range(args.n):
            started = time.perf_counter()
            response = client.get(
                "/memories/search",
                headers={"Authorization": f"Bearer {args.api_key}"},
                params={"q": args.q, "session_id": args.session_id},
            )
            response.raise_for_status()
            samples.append((time.perf_counter() - started) * 1000)
    p50, p95 = percentiles(samples)
    print(f"n={len(samples)} p50={p50:.2f}ms p95={p95:.2f}ms")


if __name__ == "__main__":
    main()
