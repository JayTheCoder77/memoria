import type { ReactNode } from "react";

import { StatusPill } from "@/components/ui/StatusPill";

export function PageShell({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="min-w-0 flex-1 px-8 py-8">
      <div className="mb-8 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{title}</h1>
        <StatusPill />
      </div>
      {children}
    </section>
  );
}
