import Link from "next/link";

import { StatusPill } from "@/components/ui/StatusPill";

export function Navbar() {
  return (
    <header className="flex items-center justify-between px-6 py-5 md:px-10">
      <Link className="font-mono text-sm tracking-[0.2em] text-text-primary" href="/">
        MEMORIA
      </Link>
      <nav className="flex items-center gap-6 font-mono text-xs text-text-secondary">
        <span className="hidden lg:inline-flex">
          <StatusPill />
        </span>
        <Link href="/docs">Docs</Link>
        <Link href="/pricing">Pricing</Link>
        <Link href="/login">Sign in</Link>
        <Link
          className="btn-cut bg-accent px-4 py-2 text-bg-terminal"
          href="/login"
        >
          Get API Key
        </Link>
      </nav>
    </header>
  );
}
