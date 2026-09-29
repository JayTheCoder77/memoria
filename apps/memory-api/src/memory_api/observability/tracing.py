from __future__ import annotations

import atexit
import logging
import os
import threading
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import Span

from memory_api.observability.logging import reset_active_trace_id, set_active_trace_id

logger = logging.getLogger(__name__)

_ALLOWED_ATTRIBUTES = frozenset({"org_id", "embedder", "model", "store"})
_configure_lock = threading.Lock()
_configured = False


def _traces_endpoint(endpoint: str) -> str:
    trimmed = endpoint.rstrip("/")
    if trimmed.endswith("/v1/traces"):
        return trimmed
    return f"{trimmed}/v1/traces"


def configure_tracing() -> None:
    """Export OTLP spans only when MEMORIA_OTEL_ENDPOINT is set."""
    global _configured
    if _configured:
        return
    with _configure_lock:
        if _configured:
            return
        try:
            endpoint = os.environ.get("MEMORIA_OTEL_ENDPOINT", "").strip()
            if not endpoint:
                return
            if isinstance(trace.get_tracer_provider(), TracerProvider):
                return
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            provider = TracerProvider()
            provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter(endpoint=_traces_endpoint(endpoint)))
            )
            trace.set_tracer_provider(provider)
            atexit.register(provider.shutdown)
        except Exception:
            logger.exception("failed to configure OTLP tracing")
        finally:
            _configured = True


def _clean_attributes(attributes: dict[str, str]) -> dict[str, str]:
    return {
        key: value
        for key, value in attributes.items()
        if key in _ALLOWED_ATTRIBUTES and isinstance(value, str)
    }


@contextmanager
def _span(name: str, attributes: dict[str, str]) -> Iterator[Span]:
    configure_tracing()
    tracer = trace.get_tracer("memory_api")
    with tracer.start_as_current_span(
        name,
        attributes=attributes,
        record_exception=False,
        set_status_on_exception=False,
    ) as span:
        token = None
        context = span.get_span_context()
        if context.is_valid:
            token = set_active_trace_id(format(context.trace_id, "032x"))
        try:
            yield span
        finally:
            if token is not None:
                reset_active_trace_id(token)


def start_span(name: str, **attributes: str) -> AbstractContextManager[Span]:
    return _span(name, _clean_attributes(attributes))
