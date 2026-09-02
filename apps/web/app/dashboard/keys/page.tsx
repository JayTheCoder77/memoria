import { getServerSession } from "next-auth";
import Link from "next/link";
import { redirect } from "next/navigation";

import { authOptions } from "@/auth";

import { KeyManager } from "./key-manager";

const memoryApiUrl = process.env.MEMORY_API_URL ?? "http://127.0.0.1:8000";

type KeyRow = {
  id: string;
  key_last4: string;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
};

export default async function KeysPage() {
  const session = await getServerSession(authOptions);
  if (!session?.memoriaToken) {
    redirect("/login");
  }
  const response = await fetch(`${memoryApiUrl}/api-keys`, {
    headers: { Authorization: `Bearer ${session.memoriaToken}` },
    cache: "no-store",
  });
  const payload = response.ok
    ? ((await response.json()) as { keys: KeyRow[] })
    : { keys: [] };

  return (
    <div className="mx-auto flex min-h-full w-full max-w-5xl gap-10 px-8 py-10">
      <aside className="w-48 shrink-0 font-mono text-sm text-[#8B8B90]">
        <p className="text-[#F2F2F0]">Memoria</p>
        <nav className="mt-8 space-y-3">
          <Link href="/dashboard/memories">Memories</Link>
          <Link className="text-[#00E08F]" href="/dashboard/keys">
            API Keys
          </Link>
          <p>Settings</p>
        </nav>
      </aside>
      <section className="flex-1">
        <div className="mb-8 flex items-center justify-between">
          <p className="font-mono text-xs uppercase tracking-[0.18em] text-[#8B8B90]">
            Dashboard
          </p>
          <span className="rounded-full border border-[#232326] px-3 py-1 font-mono text-xs text-[#00E08F]">
            ● Operational
          </span>
        </div>
        <KeyManager keys={payload.keys} />
      </section>
    </div>
  );
}
