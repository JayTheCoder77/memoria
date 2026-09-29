from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

REQUEST_DURATION = Histogram(
    "memoria_request_duration_seconds",
    "HTTP request duration in seconds",
)
LLM_TOKENS = Counter(
    "memoria_llm_tokens_total",
    "LLM tokens by direction and model",
    labelnames=("direction", "model"),
)


def observe_request_duration(duration_seconds: float) -> None:
    REQUEST_DURATION.observe(duration_seconds)


def record_llm_tokens(*, model: str, input_tokens: int, output_tokens: int) -> None:
    LLM_TOKENS.labels(direction="input", model=model).inc(input_tokens)
    LLM_TOKENS.labels(direction="output", model=model).inc(output_tokens)


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
