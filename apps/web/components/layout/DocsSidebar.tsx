"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import { docsNav } from "@/lib/docs";

export function DocsSidebar({ active }: { active: string }) {
  const [q, setQ] = useState("");
  const searchRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (!needle) return docsNav;
    return docsNav
      .map((group) => ({
        ...group,
        items: group.items.filter((item) => item.title.toLowerCase().includes(needle)),
      }))
      .filter((group) => group.items.length > 0);
  }, [q]);

  return (
    <aside className="w-56 shrink-0 border-r border-border-subtle px-5 py-8">
      <Link className="font-mono text-sm tracking-[0.2em]" href="/">
        MEMORIA
      </Link>
      <label className="mt-8 block">
        <span className="sr-only">Search docs</span>
        <input
          ref={searchRef}
          className="w-full border border-border-subtle bg-bg-terminal px-3 py-2 font-mono text-xs"
          placeholder="Search  ⌘K"
          value={q}
          onChange={(event) => setQ(event.target.value)}
        />
      </label>
      <nav className="mt-8 space-y-6">
        {filtered.map((group) => (
          <div key={group.section}>
            <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-text-secondary">
              {group.section}
            </p>
            <div className="mt-3 space-y-2 font-mono text-sm">
              {group.items.map((item) => (
                <Link
                  className={
                    active === item.href
                      ? "block border-l-2 border-accent pl-3 text-accent"
                      : "block pl-3 text-text-secondary"
                  }
                  href={item.href}
                  key={item.href}
                >
                  {item.title}
                </Link>
              ))}
            </div>
          </div>
        ))}
      </nav>
    </aside>
  );
}
