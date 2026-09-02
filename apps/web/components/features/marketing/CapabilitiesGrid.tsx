import { SectionLabel } from "@/components/ui/SectionLabel";

const items = [
  {
    n: "01",
    title: "Hybrid retrieval",
    body: "Similarity, recency decay, and importance — then truncated to a token budget.",
  },
  {
    n: "02",
    title: "Dedup + consolidation",
    body: "Near-duplicates reinforce instead of cloning. Sessions merge into one memory.",
  },
  {
    n: "03",
    title: "Multi-tenant isolation",
    body: "org_id is required on every query. Cross-tenant recall is a bug, not a feature.",
  },
  {
    n: "04",
    title: "MCP-native",
    body: "remember, recall, update, forget, emit — no session state on the adapter.",
  },
  {
    n: "05",
    title: "Async extraction",
    body: "Noisy tool calls never hit the queue. Preferences and fixes become memories.",
  },
  {
    n: "06",
    title: "Google + API keys",
    body: "Humans sign in with Google. Machines use mem_… keys hashed at rest.",
  },
];

export function CapabilitiesGrid() {
  return (
    <section className="border-t border-border-subtle px-6 py-24 md:px-10">
      <div className="mx-auto max-w-5xl">
        <div className="text-center">
          <SectionLabel>Capabilities</SectionLabel>
          <h2 className="mt-6 text-4xl font-semibold">Memory that compounds.</h2>
        </div>
        <div className="mt-12 grid gap-px bg-border-subtle md:grid-cols-3">
          {items.map((item) => (
            <article className="bg-bg-base p-6" key={item.n}>
              <p className="font-mono text-xs text-accent">[ {item.n} ]</p>
              <h3 className="mt-4 text-lg font-semibold">{item.title}</h3>
              <p className="mt-3 text-sm leading-6 text-text-secondary">{item.body}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
