export function AnsiBar({
  label,
  filled,
}: {
  label: string;
  filled: number;
}) {
  const blocks = 24;
  const count = Math.max(0, Math.min(blocks, Math.round((filled / 100) * blocks)));
  return (
    <div className="flex items-center gap-4 font-mono text-xs text-text-secondary">
      <span className="w-40 shrink-0">{label}</span>
      <span className="tracking-tight text-accent">
        {"█".repeat(count)}
        <span className="text-border-subtle">{"░".repeat(blocks - count)}</span>
      </span>
    </div>
  );
}
