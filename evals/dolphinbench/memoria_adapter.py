from __future__ import annotations

import os
from typing import Any, ClassVar

import httpx


class MemoriaBenchAdapter:
    """HTTP client imported by a DolphinBench harness. Does not import DolphinBench."""

    _frozen: ClassVar[set[str]] = set()

    def __init__(
        self,
        *,
        org_id: str,
        api_key: str | None = None,
        base_url: str | None = None,
        http: httpx.Client | None = None,
    ) -> None:
        scoped_org = str(org_id).strip() if org_id is not None else ""
        if not scoped_org:
            raise ValueError("org_id is required")
        self.org_id = scoped_org
        raw_key = api_key if api_key is not None else os.environ.get("MEMORY_API_KEY", "")
        self._api_key = raw_key.strip()
        env_url = os.environ.get("MEMORY_API_URL", "").strip().rstrip("/")
        self.base_url = (base_url or env_url or "http://127.0.0.1:8000").rstrip("/")
        self._owns_http = http is None
        self._http = http or httpx.Client(base_url=self.base_url, timeout=30.0)

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def _headers(self) -> dict[str, str]:
        if not self._api_key:
            return {}
        return {"Authorization": f"Bearer {self._api_key}"}

    def _params(self, **extra: object) -> dict[str, object]:
        return {"org_id": self.org_id, **extra}

    def reset(self, persona: str) -> None:
        listed = self._http.get(
            "/memories",
            headers=self._headers(),
            params=self._params(user_id=persona),
        )
        listed.raise_for_status()
        for memory in listed.json().get("memories", []):
            deleted = self._http.delete(
                f"/memories/{memory['id']}",
                headers=self._headers(),
                params=self._params(user_id=persona),
            )
            deleted.raise_for_status()

    def ingest(self, persona: str, session_id: str, content: str) -> None:
        if persona in self._frozen:
            raise RuntimeError(f"memory is frozen for {persona}")
        queued = self._http.post(
            "/events",
            headers=self._headers(),
            json={
                "org_id": self.org_id,
                "session_id": session_id,
                "event_type": "message",
                "user_id": persona,
                "payload": {"content": content},
            },
        )
        queued.raise_for_status()
        self._wait_until_drained(persona, session_id)

    def _wait_until_drained(self, persona: str, session_id: str) -> None:
        while True:
            drained = self._http.get(
                "/events/drain",
                headers=self._headers(),
                params=self._params(user_id=persona, session_id=session_id),
            )
            drained.raise_for_status()
            payload: dict[str, Any] = drained.json()
            if payload.get("drained") is True or payload.get("pending") == 0:
                return

    def freeze(self, persona: str) -> None:
        self._frozen.add(persona)

    def context(self, persona: str, request: str, token_budget: int = 2048) -> str:
        profile = self._http.get(
            "/profile",
            headers=self._headers(),
            params=self._params(user_id=persona, token_budget=token_budget),
        )
        profile.raise_for_status()
        search = self._http.get(
            "/memories/search",
            headers=self._headers(),
            params=self._params(user_id=persona, q=request, token_budget=token_budget),
        )
        search.raise_for_status()
        parts: list[str] = []
        text = str(profile.json().get("text") or "").strip()
        if text:
            parts.append(text)
        for memory in search.json().get("memories", []):
            content = str(memory.get("content") or "").strip()
            if content:
                parts.append(content)
        return "\n".join(parts)
