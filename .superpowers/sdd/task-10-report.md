# Task 10 report: Per-org extraction instructions and categories

Status: DONE_WITH_CONCERNS

Commit: `71cef17` feat: add per-org extraction instructions

## What landed

An org can store extraction instructions and a category list. The worker passes both into `LlmExtractor` on the write path. Empty instructions leave `_LLM_SYSTEM` as the system message. When instructions or categories are set, they are appended to the user message in this order: the instructions string, `Categories: a, b, c`, then `Assign zero or more of these categories. Do not invent categories.`

`Candidate` now has `categories: list[str]`. A returned category that is not in the org list is dropped. Allowed categories are also copied onto `source_metadata["categories"]` so they survive insert.

`Org.extraction_instructions` is nullable text. `Org.categories` is JSONB, default `[]`. Migration `0012_extraction_policy` revises `0011_scopes`.

The dashboard already had a settings page for OpenRouter keys, so the textarea lives there as its own card (the OpenRouter form requires an API key). It saves through `PUT /org/extraction-policy`. `GET` returns the same shape. The session user's org is the only org written.

## TDD evidence

### RED

Command (from `apps/memory-api`), before prompt assembly and filtering:

```bash
uv run pytest tests/test_extraction.py::test_llm_extractor_appends_org_instructions_and_drops_unknown_categories tests/test_extraction.py::test_empty_instructions_keep_system_prompt_unchanged -v --tb=short
```

The first run failed because `LlmExtractor.__init__()` did not accept `instructions` (`TypeError` at the call). After the constructor stored the new arguments and did nothing with them, the same command failed on the missing behavior:

```
E   assert 'Ignore calendar small talk' in '[{"event_type": "message", "payload": {"content": "We ship on Friday."}}]'
E   assert 'Categories: shipping' in '[{"event_type": "message", "payload": {"content": "hello"}}]'
```

Policy route, before the handler existed:

```bash
uv run pytest tests/test_google_auth.py::test_extraction_policy_saves_instructions_and_categories -v --tb=line
```

```
E   AssertionError: {"detail":"Not Found"}
    assert 404 == 200
```

### GREEN

Command (step 4 of the brief):

```bash
uv run pytest tests/test_extraction.py -v
```

Result: 16 passed.

Full memory-api suite, after `uv run alembic upgrade head` (`0011_scopes` -> `0012_extraction_policy`):

```bash
uv run pytest -q --tb=line
```

Result: 196 passed, 1 warning (pre-existing Starlette/`httpx` deprecation).

`uv run ruff check` is clean on the files this task changed. `node apps/web/node_modules/typescript/bin/tsc --noEmit -p apps/web/tsconfig.json` passed. `uv run ruff check src tests` still reports a pre-existing import-order error in `services/profile.py`, which this task did not touch.

## Files changed

- `apps/memory-api/alembic/versions/0012_extraction_policy.py` (new; `revision = "0012_extraction_policy"`, `down_revision = "0011_scopes"`)
- `apps/memory-api/src/memory_api/db/models.py`
- `apps/memory-api/src/memory_api/db/identity.py`
- `apps/memory-api/src/memory_api/services/extraction.py`
- `apps/memory-api/src/memory_api/worker.py`
- `apps/memory-api/src/memory_api/schemas/auth.py`
- `apps/memory-api/src/memory_api/routers/org.py` (new)
- `apps/memory-api/src/memory_api/main.py`
- `apps/memory-api/tests/test_extraction.py`
- `apps/memory-api/tests/test_google_auth.py`
- `apps/web/lib/api-client.ts`
- `apps/web/components/features/dashboard/actions.ts`
- `apps/web/components/features/dashboard/ExtractionPolicyCard.tsx` (new)
- `apps/web/app/dashboard/settings/page.tsx`

## Self-review

- `org_id` is taken from the session user. The policy body has no org id.
- Recall is unchanged. Only the write-path extractor gained instructions and categories.
- Request logs still record route, status, and duration. They do not record instructions, prompts, or keys.
- Empty instructions with a category list keep the system message equal to `_LLM_SYSTEM` and still append `Categories: ...` on the user message.
- Unknown categories such as `not-allowed` are dropped. `shipping` is kept when it is in the org list.
- The worker is the production `LlmExtractor` call site and passes `org.extraction_instructions` and `org.categories`.

## Concerns

- `_LLM_SYSTEM` still describes a JSON object without a `categories` field. The appendix tells the model to assign categories and not invent them, and the filter reads `memories[].categories`. A live model that follows only the system schema may omit that field, so every candidate's category list stays empty. The fake-provider test covers the filter when the field is present.
- The settings card typechecks. It was not clicked through in a browser. The page redirects to Google sign-in, and no session was available.

## Fix: failed policy load

A non-OK `GET /org/extraction-policy` used to become `{ instructions: null, categories: [] }`. The settings card then rendered a saveable form, and saving it cleared stored instructions and categories.

`getExtractionPolicy` now returns `{ ok: false, error: "Could not load extraction policy" }` on any non-OK response. The card shows that error and does not render the form or a save button. A successful empty policy is unchanged and can still be saved. The extraction prompt, `_LLM_SYSTEM`, and the category JSON schema were not changed.

Covering test: `apps/web/lib/api-client.test.ts`

### RED

Command (from `apps/web`):

```bash
bun test lib/api-client.test.ts
```

```
error: expect(received).toEqual(expected)

  {
-   "error": "Could not load extraction policy",
-   "ok": false,
+   "categories": [],
+   "instructions": null,
  }

(fail) failed extraction policy load is not an empty policy
 0 pass
 1 fail
```

### GREEN

Same command:

```bash
bun test lib/api-client.test.ts
```

```
(pass) failed extraction policy load is not an empty policy
 1 pass
 0 fail
```

Relevant suite before commit, from `apps/web`:

```bash
node ./node_modules/typescript/bin/tsc --noEmit --pretty false -p ./tsconfig.json && bun test
```

Typecheck produced no errors. `bun test` result: 1 pass, 0 fail. Python was not changed, so the memory-api extraction tests were not re-run.
