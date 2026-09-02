export function DotGrid({ className = "" }: { className?: string }) {
  return <div className={`pointer-events-none absolute inset-0 dot-grid ${className}`} />;
}
