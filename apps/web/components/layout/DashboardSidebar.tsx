"use client";

import { signOut } from "next-auth/react";

import { Sidebar } from "./Sidebar";

export function DashboardSidebar({
  active,
  email,
}: {
  active: string;
  email?: string | null;
}) {
  return (
    <Sidebar
      active={active}
      footer={
        <>
          <p className="truncate font-mono text-xs text-text-secondary">
            {email ?? "signed in"}
          </p>
          <button
            className="mt-2 font-mono text-xs text-text-secondary"
            type="button"
            onClick={() => signOut({ callbackUrl: "/" })}
          >
            Sign out
          </button>
        </>
      }
    />
  );
}
