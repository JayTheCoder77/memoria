# Groq fallback for write-path LLM

**Status:** Ready for implementation  
**Parent:** `spec/v2-llm-hybrid-writes.md`  
**Date:** 2026-09-07

Regex and heuristic extractors miss most natural phrasing. Org OpenRouter BYOK
is still preferred, but 429/timeout/missing key should not drop to regex
immediately. A per-org Groq key sits in the middle of the cascade. Groq model
is fixed by the server; Settings has no Groq model field.

## Goal

On **remember enrich** and **emit worker extract** only:

1. Org OpenRouter key (existing BYOK + model), if present.
2. Org Groq key (BYOK, encrypted like OpenRouter). Model is always
   `openai/gpt-oss-20b` (or `MEMORIA_GROQ_MODEL` server default). No UI picker.
3. Existing regex / heuristic, if both skipped or failed.

Search query parsing (`derive_kv_candidates`, `derive_graph_seeds`) is unchanged.

## Non-goals

- Hosting a model on the Render web dyno
- Replacing dashboard OpenRouter BYOK
- Per-org Groq model selection
- A shared platform Groq key on Render
- Changing fusion, stores, or MCP tool shapes
- Retry/backoff loops (one attempt per provider)

## Locked decisions

| Item | Choice |
|---|---|
| Cascade | OpenRouter BYOK → Groq BYOK → regex/heuristic |
| Host | Groq OpenAI-compatible API |
| Groq model | Fixed `openai/gpt-oss-20b`; not stored per org; not shown as an editable Settings field |
| Groq key | Per-org BYOK, same encrypt/`last4` pattern as OpenRouter |
| Scope | `remember` triple enrich + worker `LlmExtractor` |
| Missing Groq key | Skip Groq; regex/heuristic after OpenRouter (or immediately if no OpenRouter key) |
| Wiring | One `complete_json` helper, not copy-pasted HTTP in two modules |

## Data model

Alembic migration on `orgs` (mirror OpenRouter, no model column):

- `groq_key_ciphertext` text nullable
- `groq_key_last4` text nullable

`GET /auth/me` adds `groq: { configured, last4 }` (no `model`).

`PUT /auth/groq` `{ "api_key": string }`. Empty string clears the key. Session auth only. Never echo the raw key.

## Settings UI

Second card next to OpenRouter: **Groq · BYOK**. Password input + save/clear. Status line `configured · …last4` or `not configured`. Copy: used when OpenRouter is missing or fails; model is fixed (`openai/gpt-oss-20b`) and not editable.

Do not add a Groq model input. Leave the OpenRouter model field as it is.

## Server configuration

| Setting | Default | Purpose |
|---|---|---|
| `groq_base_url` | `https://api.groq.com/openai/v1` | Chat completions root |
| `groq_model` | `openai/gpt-oss-20b` | Only Groq model Memoria will call |

Operators may change the model via env. Users cannot. No `MEMORIA_FALLBACK_LLM_API_KEY`.

## Helper

New module `memory_api.services.llm_json.complete_json`:

- Input: `messages`, ordered `providers` (api_key, base_url, model, optional extra headers, timeout), optional `httpx.Client`.
- Each provider: `POST {base_url}/chat/completions` with `temperature=0`, `response_format: {type: json_object}`.
- OpenRouter extra headers (`HTTP-Referer`, `X-Title`) only for OpenRouter hosts. Groq: `Authorization` + JSON only.
- Parse `choices[0].message.content` as a JSON object. Invalid → next provider.
- HTTP / timeout / transport → warning with status (no secret), next provider.
- Empty provider list or all failures → `{}`. Callers use regex/heuristic.
- Do not raise into `remember` or `run_once`.

`enrich_hybrid_triples` and `LlmExtractor` keep current prompts/schemas.

## Remember

Canonical insert unchanged. Enrich providers:

1. Org OpenRouter key + `settings.llm_base_url` + org model or `settings.llm_model`, 10s, if key exists.
2. Org Groq key + `settings.groq_base_url` + `settings.groq_model`, 10s, if key exists.

Then `resolve_*` heuristics if triples are still empty. Explicit request triples skip enrich. LLM/Groq cannot fail `201`.

## Emit worker

Build the same provider list from the org row. If at least one key exists, use `LlmExtractor` + `complete_json`. If both missing, `HeuristicExtractor`. After both LLM failures, heuristic extract. Worker still waits for batch size 10 or `session_end`.

## Failure modes

- Groq key unset → skip Groq.
- OpenRouter 429 + Groq OK → Groq result.
- Both missing or both 429 → regex/heuristic; remember still 201; worker does not stick on `pending` from an uncaught HTTP error.
- Malformed Groq JSON → skip bad items.

## Tests

Mock `httpx` (no live Groq). Include API/UI-adjacent API tests for `PUT /auth/groq` last4-not-raw and `GET /auth/me` `groq` object.

- Enrich: OpenRouter 429 then Groq 200 → Groq triples.
- Enrich: both fail → empty (regex).
- Enrich: no OpenRouter, Groq configured → Groq called.
- Enrich: no Groq ciphertext → Groq not called.
- Extractor: OpenRouter 429 + Groq success → LLM candidates.
- Extractor: both fail + preference phrasing → heuristic.
- Worker: `session_end` + Groq 200 → processed.
- Auth: save Groq key stores last4, `me.groq.model` absent.

## Docs

Update `spec/v2-llm-hybrid-writes.md` and `spec/03-architecture.md` failure modes. README/Settings copy: paste a Groq key for fallback extraction; model is not selectable.
