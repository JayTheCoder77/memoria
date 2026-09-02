import { getServerSession } from "next-auth";
import { redirect } from "next/navigation";

import { PageShell } from "@/components/layout/PageShell";
import { Card } from "@/components/ui/Card";
import { getMe } from "@/lib/api-client";
import { authOptions } from "@/lib/auth";

export default async function SettingsPage() {
  const session = await getServerSession(authOptions);
  if (!session?.memoriaToken) {
    redirect("/login");
  }
  const me = await getMe(session.memoriaToken);

  return (
    <PageShell title="Settings">
      <div className="space-y-8">
        <Card className="p-6">
          <p className="font-mono text-xs uppercase tracking-[0.18em] text-text-secondary">
            Organization
          </p>
          <p className="mt-3 text-lg">{me?.org.name ?? "—"}</p>
          <p className="mt-2 font-mono text-xs text-text-secondary">{me?.org.id}</p>
        </Card>
        <Card className="p-6">
          <p className="font-mono text-xs uppercase tracking-[0.18em] text-text-secondary">
            Google account
          </p>
          <p className="mt-3">{me?.user.name ?? session.user?.name}</p>
          <p className="mt-1 text-sm text-text-secondary">
            {me?.user.email ?? session.user?.email}
          </p>
        </Card>
        <Card className="border-danger p-6">
          <p className="font-mono text-xs uppercase tracking-[0.18em] text-danger">
            Danger zone
          </p>
          <p className="mt-3 text-sm text-text-secondary">
            Org deletion is not enabled in MVP. Revoke keys and forget memories instead.
          </p>
        </Card>
      </div>
    </PageShell>
  );
}
