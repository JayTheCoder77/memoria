from __future__ import annotations

import time
import uuid
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from memory_api.observability.logging import bind_request, clear_request, log_request_finished
from memory_api.observability.metrics import observe_request_duration


def _org_id_from_request(request: Request) -> str | None:
    org_id: Any = getattr(request.state, "org_id", None)
    if org_id is None:
        return None
    return str(org_id)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        route = request.url.path
        bind_request(request_id, None, route)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000.0
            observe_request_duration(duration_ms / 1000.0)
            log_request_finished(
                status_code=500,
                duration_ms=duration_ms,
                org_id=_org_id_from_request(request),
            )
            clear_request()
            raise
        duration_ms = (time.perf_counter() - start) * 1000.0
        observe_request_duration(duration_ms / 1000.0)
        log_request_finished(
            status_code=response.status_code,
            duration_ms=duration_ms,
            org_id=_org_id_from_request(request),
        )
        clear_request()
        return response
