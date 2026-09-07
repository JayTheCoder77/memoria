from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from memory_api.db.models import MemoryType
from memory_api.services.llm_json import LlmProvider, complete_json

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
    graph_triples: list[dict[str, Any]] = field(default_factory=list)


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
    '"memory_type":"episodic"|"semantic"|"procedural","importance":number,'
    '"kv_triples":[{"fact_type":string,"entity":string,"value":string|null}],'
    '"graph_triples":[{"subject":string,"relation":string,"object":string}]}]}. '
    "Keep preferences, decisions, facts, and reusable fixes. Skip noise. "
    "kv_triples and graph_triples are optional. An empty memories array is valid."
)


class LlmExtractor:
    def __init__(
        self,
        *,
        providers: list[LlmProvider] | None = None,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        http: httpx.Client | None = None,
        http_referer: str | None = None,
        app_title: str | None = None,
    ) -> None:
        from memory_api.config import settings

        self._http = http or httpx.Client(timeout=30.0)
        if providers is None:
            if not api_key:
                raise ValueError("api_key or providers required")
            base = (base_url or settings.llm_base_url).rstrip("/")
            providers = [
                LlmProvider(
                    api_key=api_key,
                    base_url=base,
                    model=model or settings.llm_model,
                    timeout=30.0,
                    extra_headers={
                        "HTTP-Referer": http_referer or settings.openrouter_http_referer,
                        "X-Title": app_title or settings.openrouter_app_title,
                    },
                )
            ]
        self._providers = providers
        provider = providers[0]
        self._api_key = provider.api_key
        self._model = provider.model
        self._base_url = provider.base_url

    def extract(self, events: list[dict[str, Any]]) -> list[Candidate]:
        if not events:
            return []
        payload = complete_json(
            [
                {"role": "system", "content": _LLM_SYSTEM},
                {"role": "user", "content": json.dumps(events)},
            ],
            providers=self._providers,
            http=self._http,
        )
        if not payload:
            return HeuristicExtractor().extract(events)
        try:
            memories = payload.get("memories")
            if not isinstance(memories, list):
                return HeuristicExtractor().extract(events)
            candidates: list[Candidate] = []
            for item in memories:
                if not isinstance(item, dict):
                    continue
                try:
                    memory_type = MemoryType(str(item.get("memory_type", "")))
                except ValueError:
                    continue
                text = str(item.get("content") or "").strip()
                if not text:
                    continue
                try:
                    importance = min(1.0, max(0.0, float(item.get("importance", 0.6))))
                except (TypeError, ValueError):
                    continue
                kv_triples: list[dict[str, Any]] = []
                for triple in item.get("kv_triples") or []:
                    if not isinstance(triple, dict):
                        continue
                    fact_type = str(triple.get("fact_type") or "").strip()
                    entity = str(triple.get("entity") or "").strip()
                    if not fact_type or not entity:
                        continue
                    entry: dict[str, Any] = {"fact_type": fact_type, "entity": entity}
                    if triple.get("value") is not None:
                        entry["value"] = str(triple["value"])
                    kv_triples.append(entry)
                graph_triples: list[dict[str, Any]] = []
                for triple in item.get("graph_triples") or []:
                    if not isinstance(triple, dict):
                        continue
                    subject = str(triple.get("subject") or "").strip()
                    relation = str(triple.get("relation") or "").strip()
                    object_key = str(triple.get("object") or "").strip()
                    if not subject or not relation or not object_key:
                        continue
                    gentry: dict[str, Any] = {
                        "subject": subject,
                        "relation": relation,
                        "object": object_key,
                    }
                    if triple.get("confidence") is not None:
                        try:
                            gentry["confidence"] = float(triple["confidence"])
                        except (TypeError, ValueError):
                            pass
                    graph_triples.append(gentry)
                candidates.append(
                    Candidate(
                        content=text,
                        memory_type=memory_type,
                        importance=importance,
                        source_metadata={"extractor": "llm"},
                        kv_triples=kv_triples,
                        graph_triples=graph_triples,
                    )
                )
            return candidates
        except Exception:
            return HeuristicExtractor().extract(events)


def get_extractor(*, api_key: str | None = None, model: str | None = None) -> Extractor:
    from memory_api.config import settings

    if not api_key:
        return HeuristicExtractor()
    return LlmExtractor(
        api_key=api_key,
        model=model or settings.llm_model,
        base_url=settings.llm_base_url,
    )
