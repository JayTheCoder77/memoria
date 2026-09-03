import type { ReactNode } from "react";

import { Callout } from "@/components/ui/Callout";
import { CodeBlock } from "@/components/ui/CodeBlock";
import { mcpConfigSnippet, opencodeConfigSnippet } from "@/lib/mcp-config";

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
      { href: "/docs/memory-types", title: "Memory types" },
      { href: "/docs/self-host", title: "Self-host vs hosted" },
    ],
  },
  { section: "Reference", items: [{ href: "/docs/api", title: "API reference" }] },
];

export function docsPages(): Record<string, DocsPage> {
  const cursorSnippet = mcpConfigSnippet();
  const opencodeSnippet = opencodeConfigSnippet();

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
        { id: "tools", label: "Tools" },
      ],
      body: (
        <>
          <p>
            Memoria is a hosted memory layer behind a stateless MCP adapter that runs on
            your machine. The API lives at{" "}
            <code>https://memoria-api-jw5g.onrender.com</code>. Create a key in the
            dashboard, put it in MCP env, then call remember and recall from your harness.
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
              Paste it as <code>MEMORY_API_KEY</code> in the snippet below. Replace{" "}
              <code>mem_...</code> — do not leave the placeholder.
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
            Claude Code: MCP settings / <code>.mcp.json</code>. The adapter runs locally;
            it calls the hosted API.
          </p>
          <CodeBlock code={cursorSnippet} language="json" />
          <h2 id="opencode">OpenCode</h2>
          <p>
            OpenCode does not use <code>mcpServers</code>. Put this in project{" "}
            <code>opencode.json</code> / <code>opencode.jsonc</code>, or globally in{" "}
            <code>~/.config/opencode/opencode.json</code>. Command is a single array. Env
            is <code>environment</code>. Timeout is 60s so the first <code>uvx</code> fetch
            is not killed.
          </p>
          <CodeBlock code={opencodeSnippet} language="json" />
          <h2 id="tools">Tools</h2>
          <p>
            Five tools. Org comes from the API key. Pass <code>session_id</code> per
            conversation, or set <code>MEMORY_SESSION_ID</code>. Tools never take a key.
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
                  Sync write. Deduped. Use when the agent (or you) knows this should
                  persist. <code>memory_type</code> is episodic, semantic, or procedural.
                </td>
              </tr>
              <tr className="border-t border-border-subtle align-top">
                <td className="py-3 pr-4 font-mono text-text-primary">recall</td>
                <td className="py-3">
                  Sync search (similarity + recency + importance). Query with{" "}
                  <code>q</code>.
                </td>
              </tr>
              <tr className="border-t border-border-subtle align-top">
                <td className="py-3 pr-4 font-mono text-text-primary">update</td>
                <td className="py-3">
                  Patch an existing memory by <code>memory_id</code> (content, importance,
                  or type).
                </td>
              </tr>
              <tr className="border-t border-border-subtle align-top">
                <td className="py-3 pr-4 font-mono text-text-primary">forget</td>
                <td className="py-3">Delete one memory by <code>memory_id</code>.</td>
              </tr>
              <tr className="border-t border-border-subtle align-top">
                <td className="py-3 pr-4 font-mono text-text-primary">emit</td>
                <td className="py-3">
                  Queue a harness event (<code>message</code>, <code>tool_call</code>,{" "}
                  <code>diff</code>, <code>session_end</code>). Not every emit becomes a
                  memory. Noisy tools are skipped. The worker extracts later (heuristic,
                  or your OpenRouter key). Send <code>session_end</code> to flush a short
                  session.
                </td>
              </tr>
            </tbody>
          </table>
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
            on every MCP-backed call.
          </p>
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
            Hosted is the default for MCP users. Self-host is the same API and MCP
            contract with your own Postgres.
          </p>
          <h2 id="local">Local MVP</h2>
          <p>
            docker compose up, alembic upgrade, uvicorn, next dev. Point{" "}
            <code>MEMORY_API_URL</code> at <code>http://127.0.0.1:8000</code>. See the
            repo README.
          </p>
          <h2 id="hosted">Hosted</h2>
          <p>
            Memory API: <code>https://memoria-api-jw5g.onrender.com</code>. MCP still
            runs on your machine via <code>uvx</code>. Dashboard keys are org-scoped.
            Free Render sleeps after idle — the first request after a gap can be slow.
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
              {verb("GET")} /memories/search
            </p>
            <p>
              {verb("GET")} /memories
            </p>
            <p>
              {verb("PATCH")} /memories/{"{id}"}
            </p>
            <p>
              {verb("DELETE")} /memories/{"{id}"}
            </p>
          </div>
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
                <td>Harness session scope</td>
              </tr>
              <tr className="border-t border-border-subtle">
                <td className="py-2 font-mono text-text-primary">q</td>
                <td className="font-mono">string</td>
                <td>Recall query text</td>
              </tr>
              <tr className="border-t border-border-subtle">
                <td className="py-2 font-mono text-text-primary">token_budget</td>
                <td className="font-mono">int</td>
                <td>Truncate recall payload</td>
              </tr>
            </tbody>
          </table>
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
