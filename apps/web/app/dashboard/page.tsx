import { getServerSession } from "next-auth";
import { redirect } from "next/navigation";

import { ActivityLog } from "@/components/features/dashboard/ActivityLog";
import { PageShell } from "@/components/layout/PageShell";
import { StatGrid } from "@/components/ui/StatGrid";
import { getMe, listApiKeys, listMemories } from "@/lib/api-client";
import { authOptions } from "@/lib/auth";

export default async function DashboardPage() {
  const session = await getServerSession(authOptions);
  if (!session?.memoriaToken) {
    redirect("/login");
  }
  const token = session.memoriaToken;
  const [memories, keys, me] = await Promise.all([
    listMemories(token),
    listApiKeys(token),
    getMe(token),
  ]);
  const activeKeys = keys.filter((key) => !key.revoked_at).length;

  return (
    <PageShell title="Overview">
      <p className="mb-8 text-sm text-text-secondary">
        {me ? `${me.org.name} · ${me.user.email}` : "Org session"}
      </p>
      <StatGrid
        stats={[
          { label: "Memories", value: String(memories.length), hint: "Stored for this org" },
          { label: "Recall p95", value: "<100ms", hint: "Latency target" },
          { label: "Active keys", value: String(activeKeys), hint: "Not revoked" },
          {
            label: "Requests today",
            value: "—",
            hint: "Request log is not wired yet",
          },
        ]}
      />
      <div className="mt-10">
        <ActivityLog memories={memories} />
      </div>
    </PageShell>
  );
}
