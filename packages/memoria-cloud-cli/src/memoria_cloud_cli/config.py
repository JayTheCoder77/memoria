from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tomli_w

try:
    import tomllib
except ImportError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]


CONFIG_DIR = Path.home() / ".config" / "memoria-cloud"
CONFIG_PATH = CONFIG_DIR / "config.toml"


@dataclass
class Settings:
    api_url: str | None = None
    api_key: str | None = None
    session_id: str | None = None


def load_file(path: Path | None = None) -> Settings:
    if path is None:
        path = CONFIG_PATH
    if not path.exists():
        return Settings()
    data = tomllib.loads(path.read_text())
    return Settings(
        api_url=_opt_str(data.get("api_url")),
        api_key=_opt_str(data.get("api_key")),
        session_id=_opt_str(data.get("session_id")),
    )


def save_file(settings: Settings, path: Path | None = None) -> None:
    if path is None:
        path = CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {}
    if settings.api_url:
        payload["api_url"] = settings.api_url
    if settings.api_key:
        payload["api_key"] = settings.api_key
    if settings.session_id:
        payload["session_id"] = settings.session_id
    path.write_text(tomli_w.dumps(payload))


def _opt_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def first(*values: str | None) -> str | None:
    for value in values:
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def resolve_url(*, flag: str | None, file: Settings) -> str | None:
    return first(flag, os.environ.get("MEMORY_API_URL"), file.api_url)


def resolve_key(*, flag: str | None, file: Settings) -> str | None:
    return first(flag, os.environ.get("MEMORY_API_KEY"), file.api_key)


def resolve_session(*, flag: str | None, file: Settings) -> str | None:
    return first(flag, os.environ.get("MEMORY_SESSION_ID"), file.session_id)


def redact_key(key: str | None) -> str:
    if not key:
        return "(not set)"
    if len(key) <= 8:
        return key[:3] + "…"
    return f"{key[:4]}…{key[-4:]}"
