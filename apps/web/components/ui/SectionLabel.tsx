export function SectionLabel({ children }: { children: string }) {
  return (
    <p className="inline-flex border border-accent px-2 py-1 font-mono text-[11px] uppercase tracking-[0.18em] text-accent">
      {children}
    </p>
  );
}
