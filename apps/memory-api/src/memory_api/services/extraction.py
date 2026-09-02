from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from memory_api.db.models import MemoryType

_TEXT_KEYS = ("content", "text", "summary", "message")

_PREFERENCE = re.compile(
    r"\b(prefer|always|never|we use|don't use|do not use)\b",
    re.IGNORECASE,
)
_DECISION = re.compile(r"\b(decided|decision|going with)\b", re.IGNORECASE)
_FIX = re.compile(r"\b(fixed|workaround|instead of)\b", re.IGNORECASE)


@dataclass(frozen=True)
class Candidate:
    content: str
    memory_type: MemoryType
    importance: float = 0.6
    source_metadata: dict[str, Any] = field(default_factory=dict)


class Extractor(Protocol):
    def extract(self, events: list[dict[str, Any]]) -> list[Candidate]: ...


def _event_text(payload: dict[str, Any]) -> str:
    for key in _TEXT_KEYS:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


class HeuristicExtractor:
    def extract(self, events: list[dict[str, Any]]) -> list[Candidate]:
        candidates: list[Candidate] = []
        for event in events:
            payload = event.get("payload") or {}
            text = _event_text(payload)
            if not text:
                continue
            memory_type: MemoryType | None = None
            if _FIX.search(text):
                memory_type = MemoryType.procedural
            elif _PREFERENCE.search(text) or _DECISION.search(text):
                memory_type = MemoryType.semantic
            if memory_type is None:
                continue
            candidates.append(
                Candidate(
                    content=text,
                    memory_type=memory_type,
                    source_metadata={
                        "event_type": event.get("event_type"),
                        "extractor": "heuristic",
                    },
                )
            )
        return candidates
