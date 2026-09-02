export type Stat = {
  label: string;
  value: string;
  hint?: string;
};

export function StatGrid({ stats }: { stats: Stat[] }) {
  return (
    <div className="grid border-y border-border-subtle md:grid-cols-4">
      {stats.map((stat) => (
        <div
          className="border-border-subtle px-6 py-8 md:border-r md:last:border-r-0"
          key={stat.label}
        >
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-accent">
            {stat.label}
          </p>
          <p className="mt-3 font-mono text-3xl text-text-primary">{stat.value}</p>
          {stat.hint ? (
            <p className="mt-2 text-sm text-text-secondary">{stat.hint}</p>
          ) : null}
        </div>
      ))}
    </div>
  );
}
