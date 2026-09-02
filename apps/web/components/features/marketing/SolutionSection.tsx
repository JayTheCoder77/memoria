import { SectionLabel } from "@/components/ui/SectionLabel";
import { TerminalPanel } from "@/components/ui/TerminalPanel";

export function SolutionSection() {
  return (
    <section className="border-t border-border-subtle px-6 py-24 md:px-10">
      <div className="mx-auto grid max-w-5xl gap-12 md:grid-cols-2">
        <div>
          <SectionLabel>Introducing Memoria</SectionLabel>
          <h2 className="mt-6 text-4xl font-semibold">
            A hosted memory layer your harness can actually call.
          </h2>
          <p className="mt-4 text-sm leading-6 text-text-secondary">
            Remember on purpose, or emit harness events and let extraction decide.
            Recall is scored by similarity, recency, and importance, then truncated
            to a token budget.
          </p>
          <ol className="mt-8 space-y-3 font-mono text-xs text-text-secondary">
            <li>01  Harness (Cursor, Claude Code, any MCP client)</li>
            <li>02  Stateless MCP adapter</li>
            <li>03  Memory API (auth, scoring, extraction)</li>
            <li>04  Postgres + pgvector</li>
          </ol>
        </div>
        <TerminalPanel title="session · mcp">
          <p className="text-text-secondary">$ connected · org_id scoped</p>
          <p>
            <span className="text-accent">✓</span> remember()  semantic  18ms
          </p>
          <p className="text-text-secondary">
            {"  "}“prefer pytest over unittest”
          </p>
          <p className="mt-3">
            <span className="text-accent">✓</span> recall(“test runner”)  41ms
          </p>
          <p className="text-text-secondary">
            {"  "}hit 0.91 · we prefer pytest
          </p>
          <p className="mt-3 text-accent">
            ▍<span className="cursor-blink">_</span>
          </p>
        </TerminalPanel>
      </div>
    </section>
  );
}
