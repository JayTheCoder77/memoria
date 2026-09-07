# LLM-primary hybrid writes

Remember stays a sync save of caller text. KV and graph indexes are filled by
an LLM cascade when the org has keys: **OpenRouter BYOK**, then **Groq BYOK**
(fixed `openai/gpt-oss-20b`, no model picker), then **regex/heuristic
fallback**. Missing Groq key skips Groq. Emit is unchanged on the API (queue →
worker → same three stores); the worker uses the same cascade. MCP
**instructions** tell the agent to `emit` conversation turns so the user does
not have to.

## Remember

1. Dedup/insert the `memories` row (no LLM rewrite of `content`).
2. If the request already has `kv_triples` or `graph_triples`, use those. Do not
   call the enrich LLM.
3. Else if KV or Graph is enabled: try OpenRouter BYOK (`timeout=10s`), then Groq
   BYOK if configured (`timeout=10s`), each `POST` chat/completions asking for
   JSON `{kv_triples, graph_triples}`. Attach non-empty lists from the first
   success.
4. Else / timeout / HTTP / parse failure / empty lists: existing
   `resolve_kv_triples` / `resolve_graph_triples` heuristics.
5. Fan-out failures still cannot fail remember (`201`).

## Emit

`POST /events` still only enqueues. The worker uses the same OpenRouter → Groq →
heuristic cascade as remember, then `persist_candidate` + KV + graph.

## MCP

`MCPServer(..., instructions=...)` tells the agent to `emit` `message` after
each user turn, plus important `tool_call` / `diff`, and `session_end` when the
thread ends. `remember` is only for an explicit immediate save. No paste-in
prompt file.
