import { getServerSession } from "next-auth";
import { redirect } from "next/navigation";

import { FactsTable } from "@/components/features/dashboard/FactsTable";
import { PageShell } from "@/components/layout/PageShell";
import { listKvFacts } from "@/lib/api-client";
import { authOptions } from "@/lib/auth";

export default async function FactsPage() {
  const session = await getServerSession(authOptions);
  if (!session?.memoriaToken) {
    redirect("/login");
  }
  const facts = await listKvFacts(session.memoriaToken);

  return (
    <PageShell title="Facts">
      <FactsTable facts={facts} />
    </PageShell>
  );
}
