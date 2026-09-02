import type { ReactNode } from "react";

import { CodeBlock } from "@/components/ui/CodeBlock";

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

export function docsPages(mcpSnippet: string): Record<string, DocsPage> {
  return {
    quickstart: {
      slug: "quickstart",
      title: "Quickstart",
      section: "Start",
      headings: [
        { id: "mcp", label: "MCP config" },
        { id: "remember", label: "First remember" },
        { id: "recall", label: "First recall" },
      ],
      body: (
        <>
          <p>
            Memoria is a hosted memory layer behind a stateless MCP adapter. Paste the
            config, create an API key, then call remember and recall from your harness.
          </p>
          <h2 id="mcp">MCP config</h2>
          <p>Drop this into Cursor or Claude Code. Replace the path and keep MEMORY_API_URL pointed at the API.</p>
          <CodeBlock code={mcpSnippet} language="json" />
          <h2 id="remember">First remember</h2>
          <CodeBlock
            language="python"
            code={`remember(
  org_id="<org>",
  session_id="sess-1",
  api_key="mem_...",
  content="We prefer pytest over unittest",
  memory_type="semantic",
)`}
          />
          <h2 id="recall">First recall</h2>
          <CodeBlock
            language="python"
            code={`recall(
  org_id="<org>",
  session_id="sess-1",
  api_key="mem_...",
  q="what test runner do we use?",
)`}
          />
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
            MVP is self-host first: Docker Postgres, Memory API, MCP server, Next.js
            dashboard. Hosted is the same binary, different DATABASE_URL.
          </p>
          <h2 id="local">Local MVP</h2>
          <p>docker compose up, alembic upgrade, uvicorn, next dev. See the repo README.</p>
          <h2 id="hosted">Hosted</h2>
          <p>
            Same API and MCP contract. You still generate org-scoped keys. Nothing in
            the protocol assumes localhost.
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
