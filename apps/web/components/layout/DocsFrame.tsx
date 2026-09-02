"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { DocsSidebar } from "@/components/layout/DocsSidebar";
import { StatusPill } from "@/components/ui/StatusPill";

export function DocsFrame({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="flex min-h-full flex-1">
      <DocsSidebar active={pathname} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between border-b border-border-subtle px-8 py-4">
          <p className="font-mono text-xs text-text-secondary">Docs</p>
          <div className="flex items-center gap-4 font-mono text-xs">
            <StatusPill label="v0 · MVP" />
            <Link className="text-text-secondary" href="/login">
              Sign in
            </Link>
          </div>
        </div>
        {children}
      </div>
    </div>
  );
}
