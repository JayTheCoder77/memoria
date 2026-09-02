import type { ReactNode } from "react";

export function Card({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={`border border-border-subtle bg-bg-raised ${className}`}>{children}</div>
  );
}
