import Link from "next/link";
import type { ReactNode } from "react";

const items = [
  { href: "/dashboard", label: "Overview" },
  { href: "/dashboard/memories", label: "Memories" },
  { href: "/dashboard/keys", label: "API Keys" },
  { href: "/dashboard/settings", label: "Settings" },
];

export function Sidebar({
  active,
  footer,
}: {
  active: string;
  footer?: ReactNode;
}) {
  return (
    <aside className="flex w-52 shrink-0 flex-col border-r border-border-subtle px-5 py-8">
      <Link className="font-mono text-sm tracking-[0.2em] text-text-primary" href="/">
        MEMORIA
      </Link>
      <nav className="mt-10 space-y-3 font-mono text-sm text-text-secondary">
        {items.map((item) => (
          <Link
            className={
              active === item.href
                ? "block border-l-2 border-accent pl-3 text-accent"
                : "block pl-3"
            }
            href={item.href}
            key={item.href}
          >
            {item.label}
          </Link>
        ))}
      </nav>
      <div className="mt-auto pt-8">{footer}</div>
    </aside>
  );
}
