# LLM-primary hybrid writes

Remember stays a sync save of caller text. KV and graph indexes are filled by
**one OpenRouter call** when the org has a key; **regex is fallback**. Emit is
unchanged on the API (queue → worker → same three stores). MCP **instructions**
tell the agent to `emit` conversation turns so the user does not have to.

## Remember

1. Dedup/insert the `memories` row (no LLM rewrite of `content`).
2. If the request already has `kv_triples` or `graph_triples`, use those. Do not
   call the enrich LLM.
3. Else if KV or Graph is enabled and `_org_llm_key` returns a key: `POST`
   chat/completions (`timeout=10s`) asking for JSON
   `{kv_triples, graph_triples}`. Attach non-empty lists to the candidate.
4. Else / timeout / HTTP / parse failure / empty lists: existing
   `resolve_kv_triples` / `resolve_graph_triples` heuristics.
5. Fan-out failures still cannot fail remember (`201`).

## Emit

`POST /events` still only enqueues. The worker already uses `LlmExtractor` when
the org key exists (heuristic otherwise), then `persist_candidate` + KV + graph.
No worker change required.

## MCP

`MCPServer(..., instructions=...)` tells the agent to `emit` `message` after
each user turn, plus important `tool_call` / `diff`, and `session_end` when the
thread ends. `remember` is only for an explicit immediate save. No paste-in
prompt file.
