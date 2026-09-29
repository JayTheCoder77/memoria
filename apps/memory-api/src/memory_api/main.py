from __future__ import annotations

import logging
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from memory_api.config import settings
from memory_api.observability.logging import configure_logging
from memory_api.observability.metrics import render_metrics
from memory_api.observability.middleware import RequestLoggingMiddleware
from memory_api.routers import api_keys, auth, events, health, indexes, memories, profile
from memory_api.services.embedding import get_embedder
from memory_api.worker import tick

configure_logging()

logger = logging.getLogger(__name__)


def _worker_loop(stop: threading.Event) -> None:
    embedder = get_embedder()
    while not stop.is_set():
        try:
            created = tick(embedder=embedder)
            if created:
                logger.info("extracted %s memories", created)
        except Exception:
            logger.exception("worker tick failed")
        stop.wait(2)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    get_embedder()
    stop = threading.Event()
    thread: threading.Thread | None = None
    if settings.run_worker:
        thread = threading.Thread(target=_worker_loop, args=(stop,), daemon=True)
        thread.start()
        logger.info("in-process extraction worker started")
    yield
    stop.set()
    if thread is not None:
        thread.join(timeout=5)


app = FastAPI(title="Memoria Memory API", lifespan=lifespan)
app.add_middleware(RequestLoggingMiddleware)
origins = [item.strip() for item in settings.cors_origins.split(",") if item.strip()]
if origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get("/metrics")
def metrics() -> Response:
    body, content_type = render_metrics()
    return Response(content=body, media_type=content_type)


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(api_keys.router)
app.include_router(events.router)
app.include_router(memories.router)
app.include_router(indexes.router)
app.include_router(profile.router)
