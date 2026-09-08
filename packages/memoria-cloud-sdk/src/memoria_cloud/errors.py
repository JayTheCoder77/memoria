from __future__ import annotations


class MemoriaError(Exception):
    """Base error for Memory API failures."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class MemoriaAuthError(MemoriaError):
    """401 or missing API key."""


class MemoriaNotFoundError(MemoriaError):
    """404 from the Memory API."""


class MemoriaRateLimitError(MemoriaError):
    """429 from the Memory API."""
