import type { ReactNode } from "react";

export function TerminalPanel({
  title = "memoria",
  children,
  footer,
}: {
  title?: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <div className="overflow-hidden border border-border-subtle bg-bg-terminal">
      <div className="flex items-center gap-2 border-b border-border-subtle px-4 py-2">
        <span className="size-2 rounded-full bg-danger/80" />
        <span className="size-2 rounded-full bg-warning/80" />
        <span className="size-2 rounded-full bg-accent/80" />
        <p className="ml-2 font-mono text-xs text-text-secondary">{title}</p>
      </div>
      <div className="p-4 font-mono text-sm leading-6 text-text-primary">{children}</div>
      {footer}
    </div>
  );
}
