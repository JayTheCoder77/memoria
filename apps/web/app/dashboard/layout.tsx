import { getServerSession } from "next-auth";
import { redirect } from "next/navigation";
import type { ReactNode } from "react";

import { DashboardFrame } from "@/components/layout/DashboardFrame";
import { authOptions } from "@/lib/auth";

export default async function DashboardLayout({
  children,
}: {
  children: ReactNode;
}) {
  const session = await getServerSession(authOptions);
  if (!session?.memoriaToken) {
    redirect("/login");
  }

  return <DashboardFrame email={session.user?.email}>{children}</DashboardFrame>;
}
