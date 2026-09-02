import { getServerSession } from "next-auth";
import { redirect } from "next/navigation";

import { MemoriesTable } from "@/components/features/dashboard/MemoriesTable";
import { PageShell } from "@/components/layout/PageShell";
import { listMemories } from "@/lib/api-client";
import { authOptions } from "@/lib/auth";

export default async function MemoriesPage({
  searchParams,
}: {
  searchParams: Promise<{ session_id?: string; memory_type?: string; q?: string }>;
}) {
  const session = await getServerSession(authOptions);
  if (!session?.memoriaToken) {
    redirect("/login");
  }
  const params = await searchParams;
  const memories = await listMemories(session.memoriaToken, params);

  return (
    <PageShell title="Memories">
      <MemoriesTable filters={params} memories={memories} />
    </PageShell>
  );
}
