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
            For Python or Node outside a harness, skip MCP. Same key, same API.{" "}
            <code>pip install memoria-cloud-sdk</code> /{" "}
            <code>npm install memoria-cloud-sdk</code>, or{" "}
            <code>pip install memoria-cloud-cli</code>. See{" "}
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
        { id: "fields", label: "What the fields mean" },
        { id: "python", label: "Python" },
        { id: "node", label: "Node" },
        { id: "surface", label: "Methods" },
      ],
      body: (
        <>
          <p>
            Typed HTTP clients for the Memory API. Same <code>mem_...</code> key as MCP.
            Default base URL is <code>{hostedMemoryApiUrl}</code>. Published as{" "}
            <code>memoria-cloud-sdk</code> on{" "}
            <a href="https://pypi.org/project/memoria-cloud-sdk/">PyPI</a> and{" "}
            <a href="https://www.npmjs.com/package/memoria-cloud-sdk">npm</a>. Requires
            Python 3.12+ or Node 24+.
          </p>
          <h2 id="install">Install</h2>
          <p>Python:</p>
          <CodeBlock language="bash" code={`pip install memoria-cloud-sdk
# or
uv add memoria-cloud-sdk`} />
          <p>Node:</p>
          <CodeBlock
            language="bash"
            code={`npm install memoria-cloud-sdk
# or
bun add memoria-cloud-sdk`}
          />
          <h2 id="auth-env">Auth and env</h2>
          <p>
            Constructor args override env. <code>MEMORY_API_KEY</code> is required for
            writes and search. <code>MEMORY_API_URL</code> is optional (hosted default
            is used if unset). <code>health()</code> does not need a key.
          </p>
          <CodeBlock
            language="bash"
            code={`export MEMORY_API_KEY=mem_...
# optional, defaults to ${hostedMemoryApiUrl}
export MEMORY_API_URL=${hostedMemoryApiUrl}`}
          />
          <h2 id="fields">What the fields mean</h2>
          <p>
            Names match the HTTP API. Python uses keyword args; Node uses one object.
            Nothing here is SQL — <code>q</code> is a search question in plain language.
          </p>
          <table className="w-full text-left text-sm">
            <thead className="font-mono text-xs uppercase text-text-secondary">
              <tr>
                <th className="pb-2 pr-4">Field</th>
                <th className="pb-2">Meaning</th>
              </tr>
            </thead>
            <tbody className="text-text-secondary">
              <tr className="border-t border-border-subtle align-top">
                <td className="py-3 pr-4 font-mono text-text-primary">content</td>
                <td className="py-3">
                  The sentence or paragraph to store. Example:{" "}
                  <code>We prefer pytest</code>.
                </td>
              </tr>
              <tr className="border-t border-border-subtle align-top">
                <td className="py-3 pr-4 font-mono text-text-primary">session_id</td>
                <td className="py-3">
                  A label you invent for a chat, ticket, or project (for example{" "}
                  <code>s1</code> or <code>cli-demo</code>). It is not a second tenant —
                  the org still comes from the API key. Required on{" "}
                  <code>remember</code> and <code>emit</code>. On{" "}
                  <code>recall</code>, omit it to search the whole org; pass it only to
                  narrow to one label.
                </td>
              </tr>
              <tr className="border-t border-border-subtle align-top">
                <td className="py-3 pr-4 font-mono text-text-primary">memory_type</td>
                <td className="py-3">
                  <code>semantic</code> (defaults): preferences and decisions.{" "}
                  <code>episodic</code>: what happened in a session.{" "}
                  <code>procedural</code>: steps that worked. See{" "}
                  <a href="/docs/memory-types">Memory types</a>.
                </td>
              </tr>
              <tr className="border-t border-border-subtle align-top">
                <td className="py-3 pr-4 font-mono text-text-primary">importance</td>
                <td className="py-3">
                  Number from 0 to 1. Higher ranks higher in recall. Default{" "}
                  <code>0.5</code>.
                </td>
              </tr>
              <tr className="border-t border-border-subtle align-top">
                <td className="py-3 pr-4 font-mono text-text-primary">q</td>
                <td className="py-3">
                  On <code>recall</code>: the question you would type into search.
                  Example: <code>what test runner do we use?</code> or just{" "}
                  <code>pytest</code>. The API embeds that text and ranks memories. It
                  is not a keyword filter. On <code>list_memories</code>, <code>q</code>{" "}
                  is an optional substring filter and does <em>not</em> run semantic
                  search — use <code>recall</code> when you want ranked matches.
                </td>
              </tr>
              <tr className="border-t border-border-subtle align-top">
                <td className="py-3 pr-4 font-mono text-text-primary">limit</td>
                <td className="py-3">
                  Max memories to return from <code>recall</code>. Default 10.
                </td>
              </tr>
              <tr className="border-t border-border-subtle align-top">
                <td className="py-3 pr-4 font-mono text-text-primary">as_of</td>
                <td className="py-3">
                  Optional ISO timestamp. Recall using graph edges as they were at that
                  time (historical view). Example:{" "}
                  <code>2026-09-01T00:00:00Z</code>.
                </td>
              </tr>
              <tr className="border-t border-border-subtle align-top">
                <td className="py-3 pr-4 font-mono text-text-primary">explain</td>
                <td className="py-3">
                  If true, each hit includes <code>score_details</code> (vector vs KV vs
                  graph). Off by default.
                </td>
              </tr>
              <tr className="border-t border-border-subtle align-top">
                <td className="py-3 pr-4 font-mono text-text-primary">token_budget</td>
                <td className="py-3">
                  Cap how much recall text comes back (rough token count). Default 2048.
                </td>
              </tr>
              <tr className="border-t border-border-subtle align-top">
                <td className="py-3 pr-4 font-mono text-text-primary">event_type</td>
                <td className="py-3">
                  For <code>emit</code>: kind of queued event, usually{" "}
                  <code>message</code>. Also <code>tool_call</code>, <code>diff</code>,{" "}
                  <code>session_end</code>. <code>emit</code> only queues;{" "}
                  <code>remember</code> saves immediately.
                </td>
              </tr>
            </tbody>
          </table>
          <p>
            <code>kv_facts</code> / <code>kvFacts</code> lists extracted key–value rows
            (entity, fact type, value). <code>graph_edges</code> /{" "}
            <code>graphEdges</code> lists subject–relation–object triples. Both are
            filled by extraction after remember/emit, not by you on every call.
          </p>
          <h2 id="python">Python</h2>
          <CodeBlock
            language="python"
            code={`from memoria_cloud import Memoria

client = Memoria()  # reads MEMORY_API_KEY / MEMORY_API_URL

# Save a preference. session_id is a label you choose.
memory = client.remember(
    content="We prefer pytest",
    session_id="cli-demo",
    memory_type="semantic",
)

# q = the search question. Omit session_id to search the whole org.
hits = client.recall(q="what test runner do we use?", limit=5)
for row in hits.memories:
    print(row.content, row.score)

# List without embedding a query (optional substring via q=).
listed = client.list_memories(session_id="cli-demo", memory_type="semantic")`}
          />
          <h2 id="node">Node</h2>
          <CodeBlock
            language="ts"
            code={`import { Memoria } from "memoria-cloud-sdk";

const client = new Memoria();

await client.remember({
  content: "We prefer pytest",
  session_id: "cli-demo",
  memory_type: "semantic",
});

const hits = await client.recall({
  q: "what test runner do we use?",
  limit: 5,
});
for (const row of hits.memories) {
  console.log(row.content, row.score);
}`}
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
                <th className="pb-2">What it does</th>
              </tr>
            </thead>
            <tbody className="text-text-secondary">
              <tr className="border-t border-border-subtle align-top">
                <td className="py-3 pr-4 font-mono text-text-primary">remember</td>
                <td className="py-3">
                  Save text now. Then extract KV/graph. POST /memories.
                </td>
              </tr>
              <tr className="border-t border-border-subtle align-top">
                <td className="py-3 pr-4 font-mono text-text-primary">recall</td>
                <td className="py-3">
                  Ranked search from <code>q</code>. GET /memories/search.
                </td>
              </tr>
              <tr className="border-t border-border-subtle align-top">
                <td className="py-3 pr-4 font-mono text-text-primary">list_memories</td>
                <td className="py-3">
                  Browse stored rows. No embedding. GET /memories.
                </td>
              </tr>
              <tr className="border-t border-border-subtle align-top">
                <td className="py-3 pr-4 font-mono text-text-primary">kv_facts</td>
                <td className="py-3">Extracted facts for the org. GET /kv-facts.</td>
              </tr>
              <tr className="border-t border-border-subtle align-top">
                <td className="py-3 pr-4 font-mono text-text-primary">graph_edges</td>
                <td className="py-3">Extracted triples. GET /graph-edges.</td>
              </tr>
              <tr className="border-t border-border-subtle align-top">
                <td className="py-3 pr-4 font-mono text-text-primary">update</td>
                <td className="py-3">
                  Patch content, importance, or type. Re-embeds. PATCH
                  /memories/{"{id}"}.
                </td>
              </tr>
              <tr className="border-t border-border-subtle align-top">
                <td className="py-3 pr-4 font-mono text-text-primary">forget</td>
                <td className="py-3">Delete one memory. DELETE /memories/{"{id}"}.</td>
              </tr>
              <tr className="border-t border-border-subtle align-top">
                <td className="py-3 pr-4 font-mono text-text-primary">emit</td>
                <td className="py-3">
                  Queue an event for later extraction. POST /events.
                </td>
              </tr>
              <tr className="border-t border-border-subtle align-top">
                <td className="py-3 pr-4 font-mono text-text-primary">health</td>
                <td className="py-3">Liveness. GET /health. No API key.</td>
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
        { id: "fields", label: "Arguments" },
        { id: "commands", label: "Commands" },
      ],
      body: (
        <>
          <p>
            <code>memoria-cloud</code> wraps the Python SDK with Typer and Rich tables.
            Install from{" "}
            <a href="https://pypi.org/project/memoria-cloud-cli/">PyPI</a> as{" "}
            <code>memoria-cloud-cli</code> (Python 3.12+). That pulls{" "}
            <code>memoria-cloud-sdk</code>.
          </p>
          <h2 id="install">Install</h2>
          <CodeBlock language="bash" code={`pip install memoria-cloud-cli
# or
uv add memoria-cloud-cli`} />
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
          <h2 id="fields">Arguments</h2>
          <p>
            Same ideas as the SDK. The search text is a positional argument named{" "}
            <code>QUERY</code> in help; it is sent as <code>q</code>.
          </p>
          <table className="w-full text-left text-sm">
            <thead className="font-mono text-xs uppercase text-text-secondary">
              <tr>
                <th className="pb-2 pr-4">Arg / flag</th>
                <th className="pb-2">Meaning</th>
              </tr>
            </thead>
            <tbody className="text-text-secondary">
              <tr className="border-t border-border-subtle align-top">
                <td className="py-3 pr-4 font-mono text-text-primary">TEXT / QUERY</td>
                <td className="py-3">
                  For <code>remember</code>: the sentence to store. For{" "}
                  <code>recall</code>: the search question in plain language (for
                  example <code>what test runner do we use?</code>).
                </td>
              </tr>
              <tr className="border-t border-border-subtle align-top">
                <td className="py-3 pr-4 font-mono text-text-primary">--session</td>
                <td className="py-3">
                  Label for a chat or project. Required on remember/emit unless set in
                  env or config. Optional on recall (omit = whole org).
                </td>
              </tr>
              <tr className="border-t border-border-subtle align-top">
                <td className="py-3 pr-4 font-mono text-text-primary">--type</td>
                <td className="py-3">
                  On remember/update: <code>semantic</code>, <code>episodic</code>, or{" "}
                  <code>procedural</code>. On emit: event kind, default{" "}
                  <code>message</code>.
                </td>
              </tr>
              <tr className="border-t border-border-subtle align-top">
                <td className="py-3 pr-4 font-mono text-text-primary">--importance</td>
                <td className="py-3">0–1 ranking weight. Default 0.5 on remember.</td>
              </tr>
              <tr className="border-t border-border-subtle align-top">
                <td className="py-3 pr-4 font-mono text-text-primary">--limit</td>
                <td className="py-3">Max rows on recall/facts/graph. Recall default 10.</td>
              </tr>
              <tr className="border-t border-border-subtle align-top">
                <td className="py-3 pr-4 font-mono text-text-primary">--as-of</td>
                <td className="py-3">
                  ISO time for historical graph on recall. Example{" "}
                  <code>2026-09-01T00:00:00Z</code>.
                </td>
              </tr>
              <tr className="border-t border-border-subtle align-top">
                <td className="py-3 pr-4 font-mono text-text-primary">--explain</td>
                <td className="py-3">Include score breakdown on recall.</td>
              </tr>
              <tr className="border-t border-border-subtle align-top">
                <td className="py-3 pr-4 font-mono text-text-primary">-q / --query</td>
                <td className="py-3">
                  On <code>list</code> only: substring filter. Not semantic search —
                  use <code>recall</code> for that.
                </td>
              </tr>
              <tr className="border-t border-border-subtle align-top">
                <td className="py-3 pr-4 font-mono text-text-primary">ID</td>
                <td className="py-3">
                  UUID printed after remember. Pass it to update/forget.
                </td>
              </tr>
            </tbody>
          </table>
          <CodeBlock
            language="bash"
            code={`memoria-cloud remember "We prefer pytest" --session cli-demo --type semantic
memoria-cloud recall "what test runner do we use?" --limit 5
memoria-cloud list --session cli-demo --type semantic
memoria-cloud facts
memoria-cloud graph`}
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
                  Ranked search. <code>--limit</code>, <code>--session</code>,{" "}
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
            query. Search is <code>GET /memories/search?q=</code> where <code>q</code>{" "}
            is a natural-language question, not a filter expression. Dashboard Google
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
              <tr className="border-t border-border-subtle align-top">
                <td className="py-2 font-mono text-text-primary">session_id</td>
                <td className="font-mono">string</td>
                <td>
                  Label you invent for a chat or project, not a second tenant. Required
                  on write. Omit on recall for org-wide search.
                </td>
              </tr>
              <tr className="border-t border-border-subtle align-top">
                <td className="py-2 font-mono text-text-primary">q</td>
                <td className="font-mono">string</td>
                <td>
                  On search: plain-language question (embedded). Example:{" "}
                  <code>what test runner do we use?</code>. On list: optional substring
                  filter, not ranked search.
                </td>
              </tr>
              <tr className="border-t border-border-subtle align-top">
                <td className="py-2 font-mono text-text-primary">memory_type</td>
                <td className="font-mono">string</td>
                <td>
                  <code>semantic</code>, <code>episodic</code>, or{" "}
                  <code>procedural</code>.
                </td>
              </tr>
              <tr className="border-t border-border-subtle align-top">
                <td className="py-2 font-mono text-text-primary">as_of</td>
                <td className="font-mono">datetime</td>
                <td>Optional ISO time. Historical graph edges on recall/search.</td>
              </tr>
              <tr className="border-t border-border-subtle align-top">
                <td className="py-2 font-mono text-text-primary">token_budget</td>
                <td className="font-mono">int</td>
                <td>Cap how much recall text is returned. Default 2048.</td>
              </tr>
              <tr className="border-t border-border-subtle align-top">
                <td className="py-2 font-mono text-text-primary">limit</td>
                <td className="font-mono">int</td>
                <td>Max hits on recall. Default 10.</td>
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
