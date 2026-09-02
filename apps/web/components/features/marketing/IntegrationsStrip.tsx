const harnesses = ["Claude Code", "Cursor", "LangGraph", "any MCP client"];

export function IntegrationsStrip() {
  return (
    <section className="border-t border-border-subtle px-6 py-16 md:px-10">
      <p className="text-center font-mono text-xs uppercase tracking-[0.18em] text-text-secondary">
        Works with
      </p>
      <div className="mx-auto mt-8 flex max-w-4xl flex-wrap items-center justify-center gap-3">
        {harnesses.map((name) => (
          <span
            className="border border-border-subtle px-4 py-2 font-mono text-xs text-text-primary"
            key={name}
          >
            {name}
          </span>
        ))}
      </div>
    </section>
  );
}
