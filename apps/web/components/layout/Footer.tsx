import Link from "next/link";

import { StatusPill } from "@/components/ui/StatusPill";

export function Footer() {
  return (
    <footer className="border-t border-border-subtle px-6 py-12 md:px-10">
      <div className="grid gap-10 md:grid-cols-5">
        <div className="md:col-span-2">
          <p className="font-mono text-sm tracking-[0.2em]">MEMORIA</p>
          <p className="mt-3 max-w-sm text-sm text-text-secondary">
            Memory infrastructure for AI agent harnesses.
          </p>
        </div>
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.18em] text-text-secondary">
            Product
          </p>
          <div className="mt-3 space-y-2 text-sm">
            <Link className="block" href="/docs">
              Quickstart
            </Link>
            <Link className="block" href="/dashboard">
              Dashboard
            </Link>
          </div>
        </div>
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.18em] text-text-secondary">
            Docs
          </p>
          <div className="mt-3 space-y-2 text-sm">
            <Link className="block" href="/docs/auth">
              Authentication
            </Link>
            <Link className="block" href="/docs/api">
              API reference
            </Link>
          </div>
        </div>
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.18em] text-text-secondary">
            Company
          </p>
          <div className="mt-3 space-y-2 text-sm text-text-secondary">
            <p>Legal</p>
            <p>Privacy</p>
          </div>
        </div>
      </div>
      <div className="mt-10 flex flex-wrap items-center justify-between gap-4">
        <p className="font-mono text-xs text-text-secondary">© 2026 Memoria</p>
        <StatusPill label="All systems operational" />
      </div>
    </footer>
  );
}
