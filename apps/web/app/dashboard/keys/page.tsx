import { getServerSession } from "next-auth";
import { redirect } from "next/navigation";

import { ApiKeysList } from "@/components/features/dashboard/ApiKeysList";
import { PageShell } from "@/components/layout/PageShell";
import { listApiKeys } from "@/lib/api-client";
import { authOptions } from "@/lib/auth";

export default async function KeysPage() {
  const session = await getServerSession(authOptions);
  if (!session?.memoriaToken) {
    redirect("/login");
  }
  const keys = await listApiKeys(session.memoriaToken);

  return (
    <PageShell title="API Keys">
      <ApiKeysList keys={keys} />
    </PageShell>
  );
}
