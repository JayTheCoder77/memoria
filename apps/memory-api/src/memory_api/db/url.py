from __future__ import annotations

from typing import Any


def sqlalchemy_url(raw: str) -> str:
    url = raw.strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def engine_kwargs(url: str) -> dict[str, Any]:
    kwargs: dict[str, Any] = {"pool_pre_ping": True}
    connect_args: dict[str, Any] = {}
    if "neon.tech" in url:
        connect_args["sslmode"] = "require"
    if "-pooler" in url:
        connect_args["prepare_threshold"] = None
    if connect_args:
        kwargs["connect_args"] = connect_args
    return kwargs
