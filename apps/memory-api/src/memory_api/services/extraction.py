from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

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
    kv_triples: list[dict[str, Any]] = field(default_factory=list)


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


_LLM_SYSTEM = (
    "Extract durable memories from harness events. "
    'Return JSON {"memories":[{"content":string,'
    '"memory_type":"episodic"|"semantic"|"procedural","importance":number}]}. '
    "Keep preferences, decisions, facts, and reusable fixes. Skip noise. "
    "An empty memories array is valid."
)


class LlmExtractor:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str | None = None,
        http: httpx.Client | None = None,
        http_referer: str | None = None,
        app_title: str | None = None,
    ) -> None:
        from memory_api.config import settings

        self._api_key = api_key
        self._model = model
        self._base_url = (base_url or settings.llm_base_url).rstrip("/")
        self._http = http or httpx.Client(timeout=30.0)
        self._http_referer = http_referer or settings.openrouter_http_referer
        self._app_title = app_title or settings.openrouter_app_title

    def extract(self, events: list[dict[str, Any]]) -> list[Candidate]:
        if not events:
            return []
        response = self._http.post(
            f"{self._base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": self._http_referer,
                "X-Title": self._app_title,
            },
            json={
                "model": self._model,
                "temperature": 0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": _LLM_SYSTEM},
                    {"role": "user", "content": json.dumps(events)},
                ],
            },
        )
        response.raise_for_status()
        raw = response.json()["choices"][0]["message"]["content"] or "{}"
        payload = json.loads(raw)
        candidates: list[Candidate] = []
        for item in payload.get("memories") or []:
            if not isinstance(item, dict):
                continue
            try:
                memory_type = MemoryType(str(item.get("memory_type", "")))
            except ValueError:
                continue
            text = str(item.get("content") or "").strip()
            if not text:
                continue
            importance = min(1.0, max(0.0, float(item.get("importance", 0.6))))
            candidates.append(
                Candidate(
                    content=text,
                    memory_type=memory_type,
                    importance=importance,
                    source_metadata={"extractor": "llm", "provider": "openrouter"},
                )
            )
        return candidates


def get_extractor(*, api_key: str | None = None, model: str | None = None) -> Extractor:
    from memory_api.config import settings

    if not api_key:
        return HeuristicExtractor()
    return LlmExtractor(
        api_key=api_key,
        model=model or settings.llm_model,
        base_url=settings.llm_base_url,
    )
