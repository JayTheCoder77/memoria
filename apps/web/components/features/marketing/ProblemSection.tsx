import { SectionLabel } from "@/components/ui/SectionLabel";

const problems = [
  {
    n: "001",
    title: "Every session starts from zero",
    body: "Context dies when the process ends. The next run re-reads the same files and re-asks the same questions.",
  },
  {
    n: "002",
    title: "Context windows blow up",
    body: "Dumping the repo into the prompt is slow, expensive, and still misses the decision you made last Tuesday.",
  },
  {
    n: "003",
    title: "Fixes get forgotten",
    body: "The same bug is solved twice because the workaround never became a memory the harness could recall.",
  },
];

export function ProblemSection() {
  return (
    <section className="px-6 py-24 md:px-10">
      <div className="mx-auto max-w-5xl">
        <SectionLabel>The problem</SectionLabel>
        <h2 className="mt-6 max-w-3xl text-4xl font-semibold">
          Agents are brilliant in the moment and amnesiac by default.
        </h2>
        <div className="mt-12 grid border border-border-subtle md:grid-cols-3">
          {problems.map((item) => (
            <article
              className="border-border-subtle p-6 md:border-r md:last:border-r-0"
              key={item.n}
            >
              <p className="font-mono text-xs text-accent">{item.n}</p>
              <h3 className="mt-4 text-lg font-semibold">{item.title}</h3>
              <p className="mt-3 text-sm leading-6 text-text-secondary">{item.body}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
