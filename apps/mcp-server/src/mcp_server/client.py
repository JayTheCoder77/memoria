from __future__ import annotations

from typing import Any

import httpx


class MemoryApiClient:
    def __init__(self, http: httpx.Client) -> None:
        self._http = http

    def _headers(self, api_key: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {api_key}"}

    def remember(
        self,
        *,
        api_key: str,
        session_id: str,
        memory_type: str,
        content: str,
        importance: float = 0.5,
        source_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = self._http.post(
            "/memories",
            headers=self._headers(api_key),
            json={
                "session_id": session_id,
                "memory_type": memory_type,
                "content": content,
                "importance": importance,
                "source_metadata": source_metadata or {},
            },
        )
        response.raise_for_status()
        return response.json()

    def recall(
        self,
        *,
        api_key: str,
        session_id: str,
        q: str,
        limit: int = 10,
    ) -> dict[str, Any]:
        response = self._http.get(
            "/memories/search",
            headers=self._headers(api_key),
            params={"q": q, "session_id": session_id, "limit": limit},
        )
        response.raise_for_status()
        return response.json()

    def update(
        self,
        *,
        api_key: str,
        memory_id: str,
        content: str | None = None,
        importance: float | None = None,
        memory_type: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if content is not None:
            payload["content"] = content
        if importance is not None:
            payload["importance"] = importance
        if memory_type is not None:
            payload["memory_type"] = memory_type
        response = self._http.patch(
            f"/memories/{memory_id}",
            headers=self._headers(api_key),
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    def forget(self, *, api_key: str, memory_id: str) -> None:
        response = self._http.delete(
            f"/memories/{memory_id}",
            headers=self._headers(api_key),
        )
        response.raise_for_status()

    def emit(
        self,
        *,
        api_key: str,
        session_id: str,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = self._http.post(
            "/events",
            headers=self._headers(api_key),
            json={
                "session_id": session_id,
                "event_type": event_type,
                "payload": payload or {},
            },
        )
        response.raise_for_status()
        return response.json()
