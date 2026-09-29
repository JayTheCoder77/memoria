from __future__ import annotations

import logging
import sys
from contextvars import ContextVar, Token
from typing import Any

import structlog

REDACT_KEYS = frozenset(
    {
        "content",
        "prompt",
        "api_key",
        "authorization",
        "ciphertext",
        "kv_triples",
        "graph_triples",
    }
)

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_org_id: ContextVar[str | None] = ContextVar("org_id", default=None)
_route: ContextVar[str | None] = ContextVar("route", default=None)
_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)

_configured = False


def _redact_sensitive_keys(
    _logger: Any,
    _method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    for key in REDACT_KEYS:
        event_dict.pop(key, None)
    return event_dict


def _merge_request_context(
    _logger: Any,
    _method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    request_id = _request_id.get()
    if request_id is not None:
        event_dict.setdefault("request_id", request_id)
    org_id = _org_id.get()
    if "org_id" not in event_dict:
        event_dict["org_id"] = org_id
    route = _route.get()
    if route is not None:
        event_dict.setdefault("route", route)
    trace_id = _trace_id.get()
    if trace_id is not None or "trace_id" not in event_dict:
        event_dict["trace_id"] = trace_id
    return event_dict


def configure_logging() -> None:
    global _configured
    if _configured:
        return
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _merge_request_context,
            structlog.processors.add_log_level,
            _redact_sensitive_keys,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )
    _configured = True


def set_active_trace_id(trace_id: str) -> Token[str | None]:
    return _trace_id.set(trace_id)


def reset_active_trace_id(token: Token[str | None]) -> None:
    _trace_id.reset(token)


def bind_org_id(org_id: str) -> None:
    _org_id.set(org_id)
    structlog.contextvars.bind_contextvars(org_id=org_id)


def bind_request(request_id: str, org_id: str | None, route: str) -> None:
    _request_id.set(request_id)
    _org_id.set(org_id)
    _route.set(route)
    _trace_id.set(None)
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        org_id=org_id,
        route=route,
        trace_id=None,
    )


def clear_request() -> None:
    _request_id.set(None)
    _org_id.set(None)
    _route.set(None)
    _trace_id.set(None)
    structlog.contextvars.clear_contextvars()


def log_request_finished(
    *,
    status_code: int,
    duration_ms: float,
    org_id: str | None,
) -> None:
    request_id = _request_id.get()
    route = _route.get()
    if request_id is None or route is None:
        return
    _org_id.set(org_id)
    structlog.contextvars.bind_contextvars(org_id=org_id)
    log = structlog.get_logger()
    log.info(
        "request_finished",
        request_id=request_id,
        trace_id=_trace_id.get(),
        org_id=org_id,
        route=route,
        status_code=status_code,
        duration_ms=duration_ms,
    )
