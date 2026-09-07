# Groq BYOK Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On remember enrich and emit extraction, try org OpenRouter BYOK, then org Groq BYOK (fixed `llama-3.1-8b-instant`, no model picker), then regex/heuristic.

**Architecture:** One OpenAI-compatible `complete_json` helper walks an ordered `list[LlmProvider]`. Remember and `LlmExtractor` build that list from the org row. Groq key is stored encrypted on `orgs` like OpenRouter, without a model column. Settings gets a Groq key card only.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, httpx, Next.js Settings UI, pytest.

## Global Constraints

- Cascade: OpenRouter BYOK → Groq BYOK → regex/heuristic
- Groq model is never per-org and never an editable Settings field; always `settings.groq_model` (default `llama-3.1-8b-instant`)
- No shared platform Groq API key env
- Search `derive_kv_candidates` / `derive_graph_seeds` unchanged
- `remember` still returns 201 if LLMs fail
- Tests mock httpx; no live Groq/OpenRouter
- Work from `/Users/jayant/projects/memoria`. Memory API tests: `cd apps/memory-api && uv run pytest`
- Do not edit this plan file

## File map

| File | Role |
|---|---|
| `apps/memory-api/src/memory_api/services/llm_json.py` | `LlmProvider`, `complete_json` |
| `apps/memory-api/src/memory_api/services/org_llm.py` | Build provider list from `Org` |
| `apps/memory-api/src/memory_api/services/hybrid_triples.py` | Enrich via `complete_json` |
| `apps/memory-api/src/memory_api/services/extraction.py` | `LlmExtractor` via `complete_json` then heuristic |
| `apps/memory-api/src/memory_api/worker.py` | Use `org_chat_providers` |
| `apps/memory-api/src/memory_api/routers/memories.py` | Pass providers into enrich |
| `apps/memory-api/src/memory_api/routers/auth.py` | `PUT /auth/groq`, `me.groq` |
| `apps/memory-api/src/memory_api/db/models.py` + Alembic `0007_groq_byok.py` | `groq_key_ciphertext`, `groq_key_last4` |
| `apps/web/.../GroqCard.tsx` + settings page | BYOK UI, no model input |

---

### Task 1: `complete_json` helper

**Files:**
- Create: `apps/memory-api/src/memory_api/services/llm_json.py`
- Test: `apps/memory-api/tests/test_llm_json.py`

**Interfaces:**
- Produces: `LlmProvider(api_key: str, base_url: str, model: str, timeout: float = 10.0, extra_headers: dict[str, str] | None = None)`
- Produces: `complete_json(messages: list[dict[str, str]], *, providers: list[LlmProvider], http: httpx.Client | None = None) -> dict[str, Any]`

- [ ] **Step 1: Write failing tests**

```python
import httpx

from memory_api.services.llm_json import LlmProvider, complete_json


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_complete_json_uses_first_successful_provider() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if "openrouter" in str(request.url):
            return httpx.Response(429, json={"error": "rate"})
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"ok": true}'}}]},
        )

    payload = complete_json(
        [{"role": "user", "content": "hi"}],
        providers=[
            LlmProvider(
                api_key="or",
                base_url="https://openrouter.ai/api/v1",
                model="openai/gpt-4o-mini",
            ),
            LlmProvider(
                api_key="g",
                base_url="https://api.groq.com/openai/v1",
                model="llama-3.1-8b-instant",
            ),
        ],
        http=_client(handler),
    )
    assert payload == {"ok": True}
    assert any("openrouter" in url for url in seen)
    assert any("groq" in url for url in seen)


def test_complete_json_all_fail_returns_empty_object() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "no"})

    payload = complete_json(
        [{"role": "user", "content": "hi"}],
        providers=[
            LlmProvider(api_key="g", base_url="https://api.groq.com/openai/v1", model="x")
        ],
        http=_client(handler),
    )
    assert payload == {}


def test_complete_json_skips_empty_provider_list() -> None:
    assert complete_json([{"role": "user", "content": "hi"}], providers=[]) == {}
```

- [ ] **Step 2: Run tests — expect FAIL (import error)**

Run: `cd apps/memory-api && uv run pytest tests/test_llm_json.py -v`

- [ ] **Step 3: Implement `llm_json.py`**

```python
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LlmProvider:
    api_key: str
    base_url: str
    model: str
    timeout: float = 10.0
    extra_headers: dict[str, str] = field(default_factory=dict)


def complete_json(
    messages: list[dict[str, str]],
    *,
    providers: list[LlmProvider],
    http: httpx.Client | None = None,
) -> dict[str, Any]:
    for provider in providers:
        if not provider.api_key.strip():
            continue
        try:
            payload = _one(messages, provider=provider, http=http)
        except Exception as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            logger.warning("LLM provider %s failed (%s)", provider.base_url, status or exc)
            continue
        if payload:
            return payload
    return {}


def _one(
    messages: list[dict[str, str]],
    *,
    provider: LlmProvider,
    http: httpx.Client | None,
) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {provider.api_key}",
        "Content-Type": "application/json",
        **provider.extra_headers,
    }
    url = f"{provider.base_url.rstrip('/')}/chat/completions"
    body = {
        "model": provider.model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": messages,
    }

    def _parse(response: httpx.Response) -> dict[str, Any]:
        response.raise_for_status()
        raw = response.json()["choices"][0]["message"]["content"] or "{}"
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return {}
        return parsed

    if http is None:
        with httpx.Client(timeout=provider.timeout) as client:
            return _parse(client.post(url, headers=headers, json=body))
    return _parse(http.post(url, headers=headers, json=body))
```

- [ ] **Step 4: Re-run tests — expect PASS**

- [ ] **Step 5: Commit** `feat: add complete_json LLM provider cascade`

---

### Task 2: Groq env + org columns

**Files:**
- Modify: `apps/memory-api/src/memory_api/config.py`
- Modify: `apps/memory-api/.env.example`
- Modify: `apps/memory-api/src/memory_api/db/models.py` (`Org`)
- Create: `apps/memory-api/alembic/versions/0007_groq_byok.py` (`down_revision = "0006_graph"`)
- Modify: `apps/memory-api/src/memory_api/db/identity.py` (`update_org_groq` on both repos)
- Test: `apps/memory-api/tests/test_hybrid_config.py`

**Interfaces:**
- Produces: `Settings.groq_base_url: str = "https://api.groq.com/openai/v1"`
- Produces: `Settings.groq_model: str = "llama-3.1-8b-instant"`
- Produces: `Org.groq_key_ciphertext`, `Org.groq_key_last4` (no groq model column)
- Produces: `IdentityRepository.update_org_groq(org, *, ciphertext: str | None, last4: str | None) -> Org`

- [ ] **Step 1: Failing config test**

```python
def test_groq_defaults() -> None:
    s = Settings()
    assert s.groq_base_url == "https://api.groq.com/openai/v1"
    assert s.groq_model == "llama-3.1-8b-instant"
```

- [ ] **Step 2: Run — FAIL AttributeError**

- [ ] **Step 3: Add settings + `.env.example` lines `MEMORIA_GROQ_BASE_URL` / `MEMORIA_GROQ_MODEL`. Migration:**

```python
def upgrade() -> None:
    op.add_column("orgs", sa.Column("groq_key_ciphertext", sa.Text(), nullable=True))
    op.add_column("orgs", sa.Column("groq_key_last4", sa.Text(), nullable=True))
```

ORM fields on `Org` matching OpenRouter ciphertext/last4 (no model). Copy `update_org_openrouter` to `update_org_groq` without a model argument.

- [ ] **Step 4: `uv run pytest tests/test_hybrid_config.py -v` PASS. `uv run ruff check` on touched files.**

- [ ] **Step 5: Commit** `feat: add org Groq BYOK columns and groq model settings`

---

### Task 3: `PUT /auth/groq` and `me.groq`

**Files:**
- Modify: `apps/memory-api/src/memory_api/schemas/auth.py`
- Modify: `apps/memory-api/src/memory_api/routers/auth.py`
- Modify: `apps/memory-api/tests/test_google_auth.py`

**Interfaces:**
- Produces: `GroqOut(configured: bool, last4: str | None = None)` — **no `model` field**
- Produces: `GroqUpdate(api_key: str | None = None)`
- Produces: `MeOut.groq: GroqOut`
- Produces: `PUT /auth/groq` → `GroqOut`

- [ ] **Step 1: Extend `test_openrouter_byok_stores_last4_not_raw_key` sibling:**

```python
def test_groq_byok_stores_last4_not_raw_key_and_omits_model(client: TestClient) -> None:
    login = client.post("/auth/google", json={"id_token": "valid-google-token"})
    assert login.status_code == 200
    saved = client.put("/auth/groq", json={"api_key": "gsk_super-secret-zz99"})
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body == {"configured": True, "last4": "zz99"}
    assert "model" not in body
    assert "super-secret" not in saved.text
    me = client.get("/auth/me")
    assert me.json()["groq"] == {"configured": True, "last4": "zz99"}
    cleared = client.put("/auth/groq", json={"api_key": ""})
    assert cleared.json() == {"configured": False, "last4": None}
```

Also set `test_auth_me_returns_user_and_org` expected `groq` to `{configured: False, last4: None}`.

- [ ] **Step 2: Run — FAIL 404 / missing field**

- [ ] **Step 3: Implement schemas + `_groq_out` + `update_groq` mirroring OpenRouter but key-only. `me()` includes `groq=_groq_out(org)`.**

- [ ] **Step 4: `uv run pytest tests/test_google_auth.py -v` PASS**

- [ ] **Step 5: Commit** `feat: expose Groq BYOK on /auth/me and PUT /auth/groq`

---

### Task 4: `org_chat_providers` + remember enrich cascade

**Files:**
- Create: `apps/memory-api/src/memory_api/services/org_llm.py`
- Modify: `apps/memory-api/src/memory_api/services/hybrid_triples.py`
- Modify: `apps/memory-api/src/memory_api/routers/memories.py`
- Modify: `apps/memory-api/tests/test_hybrid_triples.py`
- Modify: `apps/memory-api/tests/test_memories_api.py` (remember enrich tests that pass `api_key=`)

**Interfaces:**
- Produces: `org_chat_providers(org: Org | None, *, timeout: float) -> list[LlmProvider]`
- Consumes: `complete_json`, `LlmProvider`
- Changes: `enrich_hybrid_triples(content, *, providers: list[LlmProvider] | None = None, http: httpx.Client | None = None) -> tuple[list[dict], list[dict]]` — drop the old single `api_key`/`model` path (update callers/tests)

`org_chat_providers` logic:

```python
def org_chat_providers(org: Org | None, *, timeout: float) -> list[LlmProvider]:
    from memory_api.config import settings
    from memory_api.services.secrets import decrypt_secret

    providers: list[LlmProvider] = []
    if org is None:
        return providers
    if org.openrouter_key_ciphertext:
        try:
            key = decrypt_secret(org.openrouter_key_ciphertext)
        except Exception:
            logger.exception("Failed to decrypt OpenRouter key")
        else:
            providers.append(
                LlmProvider(
                    api_key=key,
                    base_url=settings.llm_base_url,
                    model=org.openrouter_model or settings.llm_model,
                    timeout=timeout,
                    extra_headers={
                        "HTTP-Referer": settings.openrouter_http_referer,
                        "X-Title": settings.openrouter_app_title,
                    },
                )
            )
    if org.groq_key_ciphertext:
        try:
            key = decrypt_secret(org.groq_key_ciphertext)
        except Exception:
            logger.exception("Failed to decrypt Groq key")
        else:
            providers.append(
                LlmProvider(
                    api_key=key,
                    base_url=settings.groq_base_url,
                    model=settings.groq_model,
                    timeout=timeout,
                )
            )
    return providers
```

`enrich_hybrid_triples`: if not `content.strip()` or not providers: return `[], []`. Else `complete_json` with system+user messages using existing `_LLM_SYSTEM`, then `_parse_kv_triples` / `_parse_graph_triples`.

`create_memory`: load `Org` from `repo._session`, `providers = org_chat_providers(org, timeout=10.0)`, pass to enrich. Delete `_org_llm_key` if unused.

- [ ] **Step 1: Tests**

`test_hybrid_triples.py`:

```python
from memory_api.services.llm_json import LlmProvider

def test_enrich_openrouter_429_then_groq() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "openrouter" in str(request.url):
            return httpx.Response(429, json={"error": "rate"})
        return httpx.Response(
            200,
            json={
                "choices": [{
                    "message": {
                        "content": (
                            '{"kv_triples":[{"fact_type":"preference","entity":"rust","value":null}],'
                            '"graph_triples":[{"subject":"user","relation":"prefers","object":"rust"}]}'
                        )
                    }
                }]
            },
        )

    kv, graph = enrich_hybrid_triples(
        "I like rust",
        providers=[
            LlmProvider(api_key="or", base_url="https://openrouter.ai/api/v1", model="x"),
            LlmProvider(api_key="g", base_url="https://api.groq.com/openai/v1", model="llama-3.1-8b-instant"),
        ],
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert kv[0]["entity"] == "rust"
    assert graph[0]["object"] == "rust"


def test_enrich_without_providers_returns_empty() -> None:
    assert enrich_hybrid_triples("We prefer pytest") == ([], [])
```

Rewrite existing enrich tests to use `providers=[LlmProvider(...)]` instead of `api_key=`.

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement helper + enrich + router**

- [ ] **Step 4: `uv run pytest tests/test_hybrid_triples.py tests/test_memories_api.py -q` PASS**

- [ ] **Step 5: Commit** `feat: cascade remember enrich through OpenRouter then Groq`

---

### Task 5: Worker / `LlmExtractor` cascade

**Files:**
- Modify: `apps/memory-api/src/memory_api/services/extraction.py`
- Modify: `apps/memory-api/src/memory_api/worker.py`
- Modify: `apps/memory-api/tests/test_extraction.py`
- Modify: `apps/memory-api/tests/test_worker.py`

**Interfaces:**
- Changes: `LlmExtractor.__init__(..., providers: list[LlmProvider] | None = None, ...)`
- If `providers` is None and `api_key` is set (existing tests): wrap as a single OpenRouter `LlmProvider` so old unit tests keep working
- `extract`: `payload = complete_json(messages, providers=self._providers, http=self._http)`; parse `memories` as today; on empty payload / parse miss, `return HeuristicExtractor().extract(events)`
- `worker.extractor_for_org`: `providers = org_chat_providers(org, timeout=30.0)`; if providers: `LlmExtractor(providers=providers, api_key="unused")` — better: make `api_key` optional when `providers` passed:

```python
def __init__(self, *, providers: list[LlmProvider] | None = None, api_key: str | None = None, model: str | None = None, ...):
    if providers is None:
        from memory_api.config import settings
        if not api_key:
            raise ValueError("api_key or providers required")
        providers = [LlmProvider(api_key=api_key, base_url=self._base_url, model=model or settings.llm_model, extra_headers={...})]
    self._providers = providers
```

`get_extractor(api_key=None)` still returns `HeuristicExtractor` when no key (tests). Worker does **not** use `get_extractor` when Groq-only: use `LlmExtractor(providers=...)`.

```python
def extractor_for_org(org_id):
    org = session.get(Org, org_id)
    providers = org_chat_providers(org, timeout=30.0)
    if not providers:
        return HeuristicExtractor()
    return LlmExtractor(providers=providers)
```

- [ ] **Step 1: Tests** — keep existing LLM parse tests with `api_key=`. Add:

```python
def test_llm_extractor_falls_back_to_groq_then_heuristic() -> None:
    # 429 then Groq JSON memories — assert extractor llm
    # both 429 + "We prefer pytest" — heuristic source_metadata
```

Worker: `session_end` + Groq mock 200 with preference memory → `processed` (reuse Task pattern from `test_worker_llm_http_error_still_extracts_with_heuristic` if present; otherwise add Groq-success case).

- [ ] **Step 2: FAIL then implement**

- [ ] **Step 3: `uv run pytest tests/test_extraction.py tests/test_worker.py -q` PASS**

- [ ] **Step 4: Commit** `feat: extract with OpenRouter then Groq then heuristic`

---

### Task 6: Dashboard Groq card + docs

**Files:**
- Modify: `apps/web/lib/api-client.ts` (`GroqStatus`, `MeResponse.groq`, `saveGroqKey`)
- Modify: `apps/web/components/features/dashboard/actions.ts`
- Create: `apps/web/components/features/dashboard/GroqCard.tsx` (copy `OpenRouterCard` minus model input; placeholder `gsk_…`)
- Modify: `apps/web/app/dashboard/settings/page.tsx`
- Modify: `spec/v2-llm-hybrid-writes.md`, `spec/03-architecture.md`, `README.md` (Settings: paste Groq key; model not selectable)

**Copy (Groq card):**
“Used when OpenRouter is missing or fails. Model is fixed to llama-3.1-8b-instant. Raw key encrypted; last 4 only.”

Status line: `configured · …last4` or `not configured`. **No model `<input>`.**

- [ ] **Step 1: Wire types + `saveGroqKey` PUT `/auth/groq` `{ api_key }` + `clearGroq` `{ api_key: "" }`**

- [ ] **Step 2: Settings page renders `<GroqCard status={me?.groq ?? { configured: false, last4: null }} />` under OpenRouter**

- [ ] **Step 3: Docs cascade paragraph**

Remember: OpenRouter then Groq then regex. Worker: same. Missing Groq key skips Groq.

- [ ] **Step 4: `cd apps/web && bunx eslint` on touched TS/TSX. `cd apps/memory-api && uv run pytest -q --ignore=tests/test_postgres_api.py`**

- [ ] **Step 5: Commit** `feat: add Settings Groq BYOK card without model picker`

---

## Spec coverage

| Spec item | Task |
|---|---|
| `complete_json` helper | 1 |
| Groq env model/base URL, no platform key | 2 |
| `orgs.groq_key_*` migration | 2 |
| `PUT /auth/groq`, `me.groq` without model | 3 |
| Remember cascade | 4 |
| Worker cascade + heuristic last | 5 |
| Settings card, no model field | 6 |
| Docs | 6 |
| Search seeds unchanged | (no task) |
