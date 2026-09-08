from __future__ import annotations

import os
from typing import Any

import httpx

from memoria_cloud.errors import (
    MemoriaAuthError,
    MemoriaError,
    MemoriaNotFoundError,
    MemoriaRateLimitError,
)
from memoria_cloud.models import EmitResult, GraphEdge, KvFact, Memory, MemorySearchResult

DEFAULT_BASE_URL = "https://memoria-api-jw5g.onrender.com"


def _detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        text = response.text.strip()
        return text or f"Memory API {response.status_code}"
    if isinstance(payload, dict) and "detail" in payload:
        return str(payload["detail"])
    return str(payload)


def _raise_for_status(response: httpx.Response) -> None:
    if response.is_success:
        return
    message = _detail(response)
    status = response.status_code
    if status == 401:
        raise MemoriaAuthError(message, status_code=status)
    if status == 404:
        raise MemoriaNotFoundError(message, status_code=status)
    if status == 429:
        raise MemoriaRateLimitError(message, status_code=status)
    raise MemoriaError(message, status_code=status)


class Memoria:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        http: httpx.Client | None = None,
        timeout: float = 30.0,
    ) -> None:
        env_url = os.environ.get("MEMORY_API_URL", "").strip().rstrip("/")
        self.base_url = (base_url or env_url or DEFAULT_BASE_URL).rstrip("/")
        self._api_key = api_key
        self._owns_http = http is None
        self._http = http or httpx.Client(base_url=self.base_url, timeout=timeout)

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> Memoria:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _resolve_key(self, *, required: bool) -> str:
        raw = self._api_key if self._api_key is not None else os.environ.get("MEMORY_API_KEY", "")
        key = raw.strip()
        if required and not key:
            raise MemoriaAuthError("MEMORY_API_KEY is not set")
        return key

    def _headers(self, *, require_key: bool = True) -> dict[str, str]:
        key = self._resolve_key(required=require_key)
        if not key:
            return {}
        return {"Authorization": f"Bearer {key}"}

    def remember(
        self,
        *,
        content: str,
        session_id: str,
        memory_type: str = "semantic",
        importance: float = 0.5,
        source_metadata: dict[str, Any] | None = None,
        kv_triples: list[dict[str, Any]] | None = None,
        graph_triples: list[dict[str, Any]] | None = None,
    ) -> Memory:
        response = self._http.post(
            "/memories",
            headers=self._headers(),
            json={
                "session_id": session_id,
                "memory_type": memory_type,
                "content": content,
                "importance": importance,
                "source_metadata": source_metadata or {},
                "kv_triples": kv_triples or [],
                "graph_triples": graph_triples or [],
            },
        )
        _raise_for_status(response)
        return Memory.model_validate(response.json())

    def recall(
        self,
        *,
        q: str,
        session_id: str | None = None,
        limit: int = 10,
        as_of: str | None = None,
        explain: bool = False,
        token_budget: int = 2048,
    ) -> MemorySearchResult:
        params: dict[str, Any] = {"q": q, "limit": limit, "token_budget": token_budget}
        if session_id:
            params["session_id"] = session_id
        if as_of:
            params["as_of"] = as_of
        if explain:
            params["explain"] = "true"
        response = self._http.get("/memories/search", headers=self._headers(), params=params)
        _raise_for_status(response)
        return MemorySearchResult.model_validate(response.json())

    def list_memories(
        self,
        *,
        session_id: str | None = None,
        memory_type: str | None = None,
        q: str | None = None,
    ) -> MemorySearchResult:
        params: dict[str, Any] = {}
        if session_id:
            params["session_id"] = session_id
        if memory_type:
            params["memory_type"] = memory_type
        if q:
            params["q"] = q
        response = self._http.get("/memories", headers=self._headers(), params=params)
        _raise_for_status(response)
        return MemorySearchResult.model_validate(response.json())

    def kv_facts(self, *, limit: int = 50, offset: int = 0) -> list[KvFact]:
        response = self._http.get(
            "/kv-facts",
            headers=self._headers(),
            params={"limit": limit, "offset": offset},
        )
        _raise_for_status(response)
        return [KvFact.model_validate(row) for row in response.json().get("facts", [])]

    def graph_edges(
        self,
        *,
        valid_only: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> list[GraphEdge]:
        response = self._http.get(
            "/graph-edges",
            headers=self._headers(),
            params={"valid_only": valid_only, "limit": limit, "offset": offset},
        )
        _raise_for_status(response)
        return [GraphEdge.model_validate(row) for row in response.json().get("edges", [])]

    def update(
        self,
        memory_id: str,
        *,
        content: str | None = None,
        importance: float | None = None,
        memory_type: str | None = None,
    ) -> Memory:
        payload: dict[str, Any] = {}
        if content is not None:
            payload["content"] = content
        if importance is not None:
            payload["importance"] = importance
        if memory_type is not None:
            payload["memory_type"] = memory_type
        response = self._http.patch(
            f"/memories/{memory_id}",
            headers=self._headers(),
            json=payload,
        )
        _raise_for_status(response)
        return Memory.model_validate(response.json())

    def forget(self, memory_id: str) -> None:
        response = self._http.delete(f"/memories/{memory_id}", headers=self._headers())
        _raise_for_status(response)

    def emit(
        self,
        *,
        session_id: str,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> EmitResult:
        response = self._http.post(
            "/events",
            headers=self._headers(),
            json={
                "session_id": session_id,
                "event_type": event_type,
                "payload": payload or {},
            },
        )
        _raise_for_status(response)
        return EmitResult.model_validate(response.json())

    def health(self) -> dict[str, str]:
        response = self._http.get("/health", headers=self._headers(require_key=False))
        _raise_for_status(response)
        return response.json()
