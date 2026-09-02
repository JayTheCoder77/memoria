"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { DashboardSidebar } from "@/components/layout/DashboardSidebar";

export function DashboardFrame({
  email,
  children,
}: {
  email?: string | null;
  children: ReactNode;
}) {
  const pathname = usePathname();
  return (
    <div className="flex min-h-full flex-1">
      <DashboardSidebar active={pathname} email={email} />
      {children}
    </div>
  );
}
