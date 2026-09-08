import type { ReactNode } from "react";

import { Callout } from "@/components/ui/Callout";
import { CodeBlock } from "@/components/ui/CodeBlock";
import { hostedMemoryApiUrl, mcpConfigSnippet, opencodeConfigSnippet } from "@/lib/mcp-config";

export type DocsPage = {
  slug: string;
  title: string;
  section: string;
  headings: { id: string; label: string }[];
  body: ReactNode;
};

const verb = (method: string) => {
  const tone =
    method === "GET"
      ? "text-accent"
      : method === "DELETE"
        ? "text-danger"
        : "text-warning";
  return (
    <span className={`rounded-full border border-border-subtle px-2 py-0.5 ${tone}`}>
      {method}
    </span>
  );
};

export const docsNav = [
  { section: "Start", items: [{ href: "/docs", title: "Quickstart" }] },
  {
    section: "Guides",
    items: [
      { href: "/docs/auth", title: "Authentication" },
      { href: "/docs/sdk", title: "Python and Node SDKs" },
      { href: "/docs/cli", title: "CLI" },
      { href: "/docs/memory-types", title: "Memory types" },
      { href: "/docs/self-host", title: "Self-host vs hosted" },
    ],
  },
  { section: "Reference", items: [{ href: "/docs/api", title: "API reference" }] },
];

export function docsPages(): Record<string, DocsPage> {
  const cursorSnippet = mcpConfigSnippet(hostedMemoryApiUrl);
  const opencodeSnippet = opencodeConfigSnippet(hostedMemoryApiUrl);

  return {
    quickstart: {
      slug: "quickstart",
      title: "Quickstart",
      section: "Start",
      headings: [
        { id: "prereqs", label: "Prerequisites" },
        { id: "key", label: "API key" },
        { id: "cursor", label: "Cursor / Claude Code" },
        { id: "opencode", label: "OpenCode" },
        { id: "scope", label: "Org vs session" },
        { id: "tools", label: "Tools" },
        { id: "writes", label: "Writes and fallbacks" },
        { id: "clients", label: "SDK and CLI" },
      ],
      body: (
        <>
          <p>
            Memoria is a hosted memory layer. Agents typically talk to it through a
            stateless MCP adapter on your machine. Scripts and apps can use the same
            HTTP API via the Python or Node SDK, or the <code>memoria-cloud</code> CLI.
            Set <code>MEMORY_API_URL</code> to <code>{hostedMemoryApiUrl}</code>. Create
            a key in the dashboard and put it in env as <code>MEMORY_API_KEY</code>.
          </p>
          <p>
            The MCP adapter tells the agent to <code>emit</code> conversation turns. Use{" "}
            <code>remember</code> when a fact must persist immediately, and{" "}
            <code>recall</code> to search.
          </p>
          <Callout>
            Put the key in MCP environment variables. Do not paste it into prompts,
            AGENTS.md, or chat.
          </Callout>
          <h2 id="prereqs">Prerequisites</h2>
          <p>
            You need <a href="https://docs.astral.sh/uv/">uv</a> so the harness can spawn{" "}
            <code>uvx</code>. uv can fetch Python 3.12+ on first run. After installing,
            restart the terminal and the harness so <code>uvx</code> is on PATH. Confirm
            with <code>uvx --version</code>.
          </p>
          <p>macOS / Linux:</p>
          <CodeBlock
            language="bash"
            code={`curl -LsSf https://astral.sh/uv/install.sh | sh`}
          />
          <p>Windows (PowerShell):</p>
          <CodeBlock
            language="powershell"
            code={`powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`}
          />
          <h2 id="key">API key</h2>
          <ol className="list-decimal space-y-2 pl-5">
            <li>Sign in to the dashboard with Google.</li>
            <li>Open Keys and create a key. Copy the <code>mem_...</code> value once.</li>
            <li>
              In MCP env set <code>MEMORY_API_URL</code> to{" "}
              <code>{hostedMemoryApiUrl}</code> and paste the key as{" "}
              <code>MEMORY_API_KEY</code>. Replace <code>mem_...</code> — do not leave
              the placeholder. Do not set <code>MEMORY_SESSION_ID</code>.
            </li>
          </ol>
          <p>
            The first <code>uvx</code> start clones the MCP adapter from GitHub. That can
            take a minute. Later starts are faster. Render may cold-start the API after
            idle, so the first remember or recall can take a few seconds.
          </p>
          <h2 id="cursor">Cursor / Claude Code</h2>
          <p>
            Cursor: <code>~/.cursor/mcp.json</code> or project <code>.cursor/mcp.json</code>.
            Claude Code: MCP settings / <code>.mcp.json</code>. The adapter runs locally.
            Env must include <code>MEMORY_API_URL</code> ={" "}
            <code>{hostedMemoryApiUrl}</code> and <code>MEMORY_API_KEY</code>.
          </p>
          <CodeBlock code={cursorSnippet} language="json" />
          <h2 id="opencode">OpenCode</h2>
          <p>
            OpenCode does not use <code>mcpServers</code>. Put this in project{" "}
            <code>opencode.json</code> / <code>opencode.jsonc</code>, or globally in{" "}
            <code>~/.config/opencode/opencode.json</code>. Command is a single array. Env
            is <code>environment</code> with <code>MEMORY_API_URL</code> ={" "}
            <code>{hostedMemoryApiUrl}</code> and <code>MEMORY_API_KEY</code>. Timeout is
            60s so the first <code>uvx</code> fetch is not killed.
          </p>
          <CodeBlock code={opencodeSnippet} language="json" />
          <h2 id="scope">Org vs session</h2>
          <p>
            Tenancy is the org on your API key. Session is a label on writes, not a
            second tenant. Do not put a session id in MCP JSON. Clients do not update
            that file when you start a new chat.
          </p>
          <table className="w-full text-left text-sm">
            <thead className="font-mono text-xs uppercase text-text-secondary">
              <tr>
                <th className="pb-2 pr-4">Scope</th>
                <th className="pb-2">How tools use it</th>
              </tr>
            </thead>
            <tbody className="text-text-secondary">
              <tr className="border-t border-border-subtle align-top">
                <td className="py-3 pr-4 font-mono text-text-primary">Org-wide</td>
                <td className="py-3">
                  Implied by <code>MEMORY_API_KEY</code>. Default <code>recall</code>{" "}
                  searches every memory in that org (any session). <code>update</code> and{" "}
                  <code>forget</code> target one row by <code>memory_id</code> inside the
                  org. Memories never cross orgs.
                </td>
              </tr>
              <tr className="border-t border-border-subtle align-top">
                <td className="py-3 pr-4 font-mono text-text-primary">Session-wide</td>
                <td className="py-3">
                  <code>remember</code> and <code>emit</code> tag writes with an auto
                  session id for this harness process. <code>emit(session_end)</code>{" "}
                  flushes extraction and starts a new id. Pass <code>session_id</code> on{" "}
                  <code>recall</code> only when you want that conversation, not the whole
                  org. Optional <code>session_id</code> on write pins a label; omit it
                  otherwise.
                </td>
              </tr>
            </tbody>
          </table>
          <h2 id="tools">Tools</h2>
          <p>
            Five tools. Org comes from the API key. Do not set{" "}
            <code>MEMORY_SESSION_ID</code> in MCP JSON. Writes get an auto session id
            for this harness process; <code>emit(session_end)</code> flushes extraction
            and starts a new one. <code>recall</code> searches the whole org unless you
            pass <code>session_id</code>. Tools never take a key.
          </p>
          <table className="w-full text-left text-sm">
            <thead className="font-mono text-xs uppercase text-text-secondary">
              <tr>
                <th className="pb-2 pr-4">Tool</th>
                <th className="pb-2">Description</th>
              </tr>
            </thead>
            <tbody className="text-text-secondary">
              <tr className="border-t border-border-subtle align-top">
                <td className="py-3 pr-4 font-mono text-text-primary">remember</td>
                <td className="py-3">
                  Immediate save of the caller text (no rewrite). Deduped. Stores the
                  canonical memory, then fills KV and graph. Use when you or the agent
                  are sure a fact must persist now. <code>memory_type</code> is episodic,
                  semantic, or procedural.
                </td>
              </tr>
              <tr className="border-t border-border-subtle align-top">
                <td className="py-3 pr-4 font-mono text-text-primary">emit</td>
                <td className="py-3">
                  Queue only. Call after user turns; do not wait for the user to ask.
                  Types: <code>message</code>, <code>tool_call</code>, <code>diff</code>,{" "}
                  <code>session_end</code>. Noisy reads/greps are skipped. Not every
                  event becomes a memory. The worker extracts later. Pending in the Event
                  Buffer until 10 events or <code>session_end</code> is normal.{" "}
                  <code>session_end</code> flushes the batch and rotates the auto session
                  id.
                </td>
              </tr>
              <tr className="border-t border-border-subtle align-top">
                <td className="py-3 pr-4 font-mono text-text-primary">recall</td>
                <td className="py-3">
                  Sync search across vector, KV, and graph, fused by relevance,
                  importance, and recency. Query with <code>q</code>. Org-wide unless you
                  pass <code>session_id</code>. Optional <code>as_of</code> (ISO datetime)
                  reads historical graph edges.
                </td>
              </tr>
              <tr className="border-t border-border-subtle align-top">
                <td className="py-3 pr-4 font-mono text-text-primary">update</td>
                <td className="py-3">
                  Patch an existing memory by <code>memory_id</code> (content, importance,
                  or type). New content is re-embedded. Does not re-run LLM extraction or
                  rewrite KV/graph.
                </td>
              </tr>
              <tr className="border-t border-border-subtle align-top">
                <td className="py-3 pr-4 font-mono text-text-primary">forget</td>
                <td className="py-3">
                  Delete one memory by <code>memory_id</code>. KV facts for that row are
                  removed. Graph edges stay; their <code>memory_id</code> is cleared.
                </td>
              </tr>
            </tbody>
          </table>
          <h2 id="writes">Writes and fallbacks</h2>
          <p>
            Paste keys in dashboard Settings. Extraction tries OpenRouter (your model),
            then Groq (fixed <code>openai/gpt-oss-20b</code>), then regex/heuristic.
            Missing Groq skips Groq. Rate limits and HTTP errors still succeed; they
            fall through. LLM/Groq cannot fail <code>remember</code>.
          </p>
          <p>
            <code>remember</code> enriches KV/graph on that request. <code>emit</code>{" "}
            only queues; the same cascade runs in the worker. Recall query parsing uses
            OpenRouter if configured, else regex — not the Groq cascade.
          </p>
          <h2 id="clients">SDK and CLI</h2>
          <p>
            For Python or Node outside a harness, skip MCP. Same key, same API. See{" "}
            <a href="/docs/sdk">Python and Node SDKs</a> and the{" "}
            <a href="/docs/cli">CLI</a>.
          </p>
        </>
      ),
    },
    auth: {
      slug: "auth",
      title: "Authentication",
      section: "Guides",
      headings: [
        { id: "google", label: "Google OAuth" },
        { id: "keys", label: "API keys" },
      ],
      body: (
        <>
          <p>Humans use Google. Machines use API keys. The Memory API owns both.</p>
          <h2 id="google">Google OAuth</h2>
          <p>
            The dashboard signs in with Auth.js. On success it posts the Google ID token
            to POST /auth/google. The API issues a session JWT used for key management
            and listing memories.
          </p>
          <h2 id="keys">API keys</h2>
          <p>
            Create keys in the dashboard. Format is mem_… — last 4 characters are stored
            for display. The plaintext is shown once. Send it as Authorization: Bearer
            on every machine call (MCP, SDK, or CLI). Put it in{" "}
            <code>MEMORY_API_KEY</code>, not in prompts or AGENTS.md.
          </p>
        </>
      ),
    },
    sdk: {
      slug: "sdk",
      title: "Python and Node SDKs",
      section: "Guides",
      headings: [
        { id: "install", label: "Install" },
        { id: "auth-env", label: "Auth and env" },
        { id: "python", label: "Python" },
        { id: "node", label: "Node" },
        { id: "surface", label: "Methods" },
      ],
      body: (
        <>
          <p>
            Typed HTTP clients for the Memory API. Same <code>mem_...</code> key as MCP.
            Default base URL is <code>{hostedMemoryApiUrl}</code>. Package names:{" "}
            <code>memoria-cloud-sdk</code> on PyPI and npm.
          </p>
          <Callout>
            Until PyPI and npm publishes land, install from the GitHub repo as below.
            The MCP adapter already uses the Python SDK in this repo.
          </Callout>
          <h2 id="install">Install</h2>
          <p>Python:</p>
          <CodeBlock
            language="bash"
            code={`pip install "git+https://github.com/JayTheCoder77/memoria.git#subdirectory=packages/memoria-cloud-sdk"`}
          />
          <p>Node (from a clone of this repo, until the npm package is published):</p>
          <CodeBlock
            language="bash"
            code={`cd packages/memoria-cloud-js
bun install
bun run build`}
          />
          <h2 id="auth-env">Auth and env</h2>
          <p>
            Constructor args override env. <code>MEMORY_API_KEY</code> is required for
            writes and search. <code>MEMORY_API_URL</code> is optional.{" "}
            <code>GET /health</code> does not require a key.
          </p>
          <h2 id="python">Python</h2>
          <CodeBlock
            language="python"
            code={`from memoria_cloud import Memoria

client = Memoria()  # MEMORY_API_URL / MEMORY_API_KEY
client.remember(content="We prefer pytest", session_id="s1")
hits = client.recall(q="pytest")
for memory in hits.memories:
    print(memory.content, memory.score)`}
          />
          <h2 id="node">Node</h2>
          <CodeBlock
            language="ts"
            code={`import { Memoria } from "memoria-cloud-sdk";

const client = new Memoria();
const hits = await client.recall({ q: "pytest" });`}
          />
          <h2 id="surface">Methods</h2>
          <p>
            Python names below. Node uses camelCase for inspect helpers (
            <code>listMemories</code>, <code>kvFacts</code>, <code>graphEdges</code>).
            Core verbs stay <code>remember</code>, <code>recall</code>,{" "}
            <code>update</code>, <code>forget</code>, <code>emit</code>,{" "}
            <code>health</code>.
          </p>
          <table className="w-full text-left text-sm">
            <thead className="font-mono text-xs uppercase text-text-secondary">
              <tr>
                <th className="pb-2 pr-4">Method</th>
                <th className="pb-2">HTTP</th>
              </tr>
            </thead>
            <tbody className="text-text-secondary">
              <tr className="border-t border-border-subtle">
                <td className="py-3 pr-4 font-mono text-text-primary">remember</td>
                <td className="py-3 font-mono">POST /memories</td>
              </tr>
              <tr className="border-t border-border-subtle">
                <td className="py-3 pr-4 font-mono text-text-primary">recall</td>
                <td className="py-3 font-mono">GET /memories/search</td>
              </tr>
              <tr className="border-t border-border-subtle">
                <td className="py-3 pr-4 font-mono text-text-primary">list_memories</td>
                <td className="py-3 font-mono">GET /memories</td>
              </tr>
              <tr className="border-t border-border-subtle">
                <td className="py-3 pr-4 font-mono text-text-primary">kv_facts</td>
                <td className="py-3 font-mono">GET /kv-facts</td>
              </tr>
              <tr className="border-t border-border-subtle">
                <td className="py-3 pr-4 font-mono text-text-primary">graph_edges</td>
                <td className="py-3 font-mono">GET /graph-edges</td>
              </tr>
              <tr className="border-t border-border-subtle">
                <td className="py-3 pr-4 font-mono text-text-primary">update</td>
                <td className="py-3 font-mono">PATCH /memories/{"{id}"}</td>
              </tr>
              <tr className="border-t border-border-subtle">
                <td className="py-3 pr-4 font-mono text-text-primary">forget</td>
                <td className="py-3 font-mono">DELETE /memories/{"{id}"}</td>
              </tr>
              <tr className="border-t border-border-subtle">
                <td className="py-3 pr-4 font-mono text-text-primary">emit</td>
                <td className="py-3 font-mono">POST /events</td>
              </tr>
              <tr className="border-t border-border-subtle">
                <td className="py-3 pr-4 font-mono text-text-primary">health</td>
                <td className="py-3 font-mono">GET /health</td>
              </tr>
            </tbody>
          </table>
          <p>
            Typed errors: 401 auth, 404 not found, 429 rate limit. Google OAuth and
            dashboard key admin are not in the SDK.
          </p>
        </>
      ),
    },
    cli: {
      slug: "cli",
      title: "CLI",
      section: "Guides",
      headings: [
        { id: "install", label: "Install" },
        { id: "config", label: "Config" },
        { id: "commands", label: "Commands" },
      ],
      body: (
        <>
          <p>
            <code>memoria-cloud</code> wraps the Python SDK with Typer and Rich tables.
            PyPI name is <code>memoria-cloud-cli</code>.
          </p>
          <h2 id="install">Install</h2>
          <CodeBlock
            language="bash"
            code={`pip install "git+https://github.com/JayTheCoder77/memoria.git#subdirectory=packages/memoria-cloud-cli"`}
          />
          <p>That pulls <code>memoria-cloud-sdk</code> as a dependency.</p>
          <h2 id="config">Config</h2>
          <p>
            Flags win over env, which wins over{" "}
            <code>~/.config/memoria-cloud/config.toml</code>. Never prints the full key.
            Exit code 2 is auth; 1 is API or usage.
          </p>
          <CodeBlock
            language="bash"
            code={`export MEMORY_API_KEY=mem_...
# optional: MEMORY_API_URL, MEMORY_SESSION_ID
memoria-cloud config --api-key mem_...
memoria-cloud --url ${hostedMemoryApiUrl} health`}
          />
          <h2 id="commands">Commands</h2>
          <table className="w-full text-left text-sm">
            <thead className="font-mono text-xs uppercase text-text-secondary">
              <tr>
                <th className="pb-2 pr-4">Command</th>
                <th className="pb-2">Maps to</th>
              </tr>
            </thead>
            <tbody className="text-text-secondary">
              <tr className="border-t border-border-subtle">
                <td className="py-3 pr-4 font-mono text-text-primary">remember TEXT</td>
                <td className="py-3">
                  Immediate save. Needs <code>--session</code>,{" "}
                  <code>MEMORY_SESSION_ID</code>, or config.
                </td>
              </tr>
              <tr className="border-t border-border-subtle">
                <td className="py-3 pr-4 font-mono text-text-primary">recall QUERY</td>
                <td className="py-3">
                  Search. <code>--limit</code>, <code>--session</code>,{" "}
                  <code>--as-of</code>, <code>--explain</code>.
                </td>
              </tr>
              <tr className="border-t border-border-subtle">
                <td className="py-3 pr-4 font-mono text-text-primary">list</td>
                <td className="py-3">List memories without embedding a query.</td>
              </tr>
              <tr className="border-t border-border-subtle">
                <td className="py-3 pr-4 font-mono text-text-primary">facts</td>
                <td className="py-3">KV facts for the org.</td>
              </tr>
              <tr className="border-t border-border-subtle">
                <td className="py-3 pr-4 font-mono text-text-primary">graph</td>
                <td className="py-3">
                  Graph edges. <code>--all</code> includes invalid edges.
                </td>
              </tr>
              <tr className="border-t border-border-subtle">
                <td className="py-3 pr-4 font-mono text-text-primary">update ID</td>
                <td className="py-3">
                  <code>--content</code>, <code>--importance</code>, <code>--type</code>.
                </td>
              </tr>
              <tr className="border-t border-border-subtle">
                <td className="py-3 pr-4 font-mono text-text-primary">forget ID</td>
                <td className="py-3">Delete one memory.</td>
              </tr>
              <tr className="border-t border-border-subtle">
                <td className="py-3 pr-4 font-mono text-text-primary">emit</td>
                <td className="py-3">
                  Queue an event. <code>--type</code>, <code>--session</code>,{" "}
                  <code>--payload</code> JSON.
                </td>
              </tr>
              <tr className="border-t border-border-subtle">
                <td className="py-3 pr-4 font-mono text-text-primary">health</td>
                <td className="py-3">GET /health</td>
              </tr>
            </tbody>
          </table>
        </>
      ),
    },
    "memory-types": {
      slug: "memory-types",
      title: "Memory types",
      section: "Guides",
      headings: [
        { id: "episodic", label: "Episodic" },
        { id: "semantic", label: "Semantic" },
        { id: "procedural", label: "Procedural" },
      ],
      body: (
        <>
          <p>Three types. Same table. Different meaning at recall time.</p>
          <h2 id="episodic">Episodic</h2>
          <p>What happened in a session — events, diffs, the trail of work.</p>
          <h2 id="semantic">Semantic</h2>
          <p>Preferences and decisions. “We use uv.” “Never commit .env.”</p>
          <h2 id="procedural">Procedural</h2>
          <p>How to do a thing — fixes, workarounds, the steps that actually worked.</p>
        </>
      ),
    },
    "self-host": {
      slug: "self-host",
      title: "Self-host vs hosted",
      section: "Guides",
      headings: [
        { id: "local", label: "Local MVP" },
        { id: "hosted", label: "Hosted" },
      ],
      body: (
        <>
          <p>
            Hosted is the default for MCP users. Self-host is the same API, MCP, SDK,
            and CLI contract with your own Postgres.
          </p>
          <h2 id="local">Local MVP</h2>
          <p>
            docker compose up, alembic upgrade, uvicorn, next dev. Point{" "}
            <code>MEMORY_API_URL</code> at <code>http://127.0.0.1:8000</code> in MCP
            env, the SDK constructor, or <code>memoria-cloud --url</code>. See the repo
            README.
          </p>
          <h2 id="hosted">Hosted</h2>
          <p>
            Memory API: set <code>MEMORY_API_URL</code> to{" "}
            <code>{hostedMemoryApiUrl}</code> (MCP env, SDK, or CLI). MCP still runs on
            your machine via <code>uvx</code>. Dashboard keys are org-scoped. Free Render
            sleeps after idle — the first request after a gap can be slow.
          </p>
        </>
      ),
    },
    api: {
      slug: "api",
      title: "API reference",
      section: "Reference",
      headings: [
        { id: "memories", label: "Memories" },
        { id: "clients", label: "SDKs and CLI" },
        { id: "auth-api", label: "Auth" },
        { id: "keys-api", label: "API keys" },
      ],
      body: (
        <>
          <h2 id="memories">Memories</h2>
          <div className="space-y-3 font-mono text-sm">
            <p>
              {verb("POST")} /memories
            </p>
            <p>
              {verb("POST")} /events
            </p>
            <p>
              {verb("GET")} /memories/search
            </p>
            <p>
              {verb("GET")} /memories
            </p>
            <p>
              {verb("GET")} /kv-facts
            </p>
            <p>
              {verb("GET")} /graph-edges
            </p>
            <p>
              {verb("PATCH")} /memories/{"{id}"}
            </p>
            <p>
              {verb("DELETE")} /memories/{"{id}"}
            </p>
            <p>
              {verb("GET")} /health
            </p>
          </div>
          <p className="mt-4 text-sm text-text-secondary">
            Machine keys (<code>mem_...</code>) work on memories, events, search, list,{" "}
            KV, graph, and health. <code>GET /memories</code> lists without embedding a
            query. Search is <code>GET /memories/search?q=</code>. Dashboard Google
            session still works for list, KV, and graph.
          </p>
          <table className="mt-6 w-full text-left text-sm">
            <thead className="font-mono text-xs uppercase text-text-secondary">
              <tr>
                <th className="pb-2">Param</th>
                <th className="pb-2">Type</th>
                <th className="pb-2">Description</th>
              </tr>
            </thead>
            <tbody className="text-text-secondary">
              <tr className="border-t border-border-subtle">
                <td className="py-2 font-mono text-text-primary">session_id</td>
                <td className="font-mono">string</td>
                <td>
                  Optional. Omit on recall for org-wide search. On write, auto-assigned
                  per harness process unless passed.
                </td>
              </tr>
              <tr className="border-t border-border-subtle">
                <td className="py-2 font-mono text-text-primary">q</td>
                <td className="font-mono">string</td>
                <td>Recall query text</td>
              </tr>
              <tr className="border-t border-border-subtle">
                <td className="py-2 font-mono text-text-primary">as_of</td>
                <td className="font-mono">datetime</td>
                <td>Optional. Historical graph edges on recall/search</td>
              </tr>
              <tr className="border-t border-border-subtle">
                <td className="py-2 font-mono text-text-primary">token_budget</td>
                <td className="font-mono">int</td>
                <td>Truncate recall payload</td>
              </tr>
            </tbody>
          </table>
          <h2 id="clients">SDKs and CLI</h2>
          <p>
            Prefer the clients over raw HTTP:{" "}
            <a href="/docs/sdk">Python and Node SDKs</a>, <a href="/docs/cli">CLI</a>.
            They send Bearer <code>mem_...</code> and map 401/404/429 to typed errors.
          </p>
          <h2 id="auth-api">Auth</h2>
          <p className="font-mono text-sm">
            {verb("POST")} /auth/google · {verb("GET")} /auth/me
          </p>
          <h2 id="keys-api">API keys</h2>
          <p className="font-mono text-sm">
            {verb("POST")} /api-keys · {verb("GET")} /api-keys · {verb("DELETE")} /api-keys/{"{id}"}
          </p>
        </>
      ),
    },
  };
}
