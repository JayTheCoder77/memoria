import { getServerSession } from "next-auth";
import { redirect } from "next/navigation";

import { GraphTable } from "@/components/features/dashboard/GraphTable";
import { PageShell } from "@/components/layout/PageShell";
import { listGraphEdges } from "@/lib/api-client";
import { authOptions } from "@/lib/auth";

export default async function GraphPage({
  searchParams,
}: {
  searchParams: Promise<{ history?: string }>;
}) {
  const session = await getServerSession(authOptions);
  if (!session?.memoriaToken) {
    redirect("/login");
  }
  const params = await searchParams;
  const showInvalid = params.history === "1";
  const edges = await listGraphEdges(session.memoriaToken, {
    valid_only: !showInvalid,
  });

  return (
    <PageShell title="Graph">
      <GraphTable edges={edges} showInvalid={showInvalid} />
    </PageShell>
  );
}
