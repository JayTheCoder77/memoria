import { Button } from "@/components/ui/Button";
import { DotGrid } from "@/components/layout/DotGrid";

const ticker = [
  "Sub-100ms recall",
  "Stateless MCP",
  "Multi-tenant",
  "Episodic",
  "Semantic",
  "Procedural",
  "Async extraction",
];

export function Hero() {
  const loop = [...ticker, ...ticker];
  return (
    <section className="relative overflow-hidden border-b border-border-subtle">
      <DotGrid />
      <div className="relative mx-auto max-w-5xl px-6 py-24 md:px-10 md:py-32">
        <p className="font-mono text-xs uppercase tracking-[0.22em] text-accent">
          Memory infrastructure for AI agents
        </p>
        <h1 className="mt-6 max-w-3xl text-5xl font-semibold tracking-tight md:text-7xl">
          Your agent forgets everything. We fixed that.
        </h1>
        <p className="mt-6 max-w-xl text-lg text-text-secondary">
          Persistent episodic, semantic, and procedural memory over a stateless MCP
          adapter — recall in under 100ms.
        </p>
        <div className="mt-10 flex flex-wrap gap-4">
          <Button href="/login">Get API Key</Button>
          <Button href="/docs" variant="secondary">
            Read the docs
          </Button>
        </div>
      </div>
      <div className="relative border-t border-border-subtle bg-accent-dim py-3">
        <div className="overflow-hidden">
          <div className="ticker-track flex w-max gap-8 font-mono text-xs uppercase tracking-[0.18em] text-text-primary">
            {loop.map((item, index) => (
              <span key={`${item}-${index}`}>
                {item} <span className="text-accent">·</span>
              </span>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
