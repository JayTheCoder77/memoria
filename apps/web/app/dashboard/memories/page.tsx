import { getServerSession } from "next-auth";
import Link from "next/link";
import { redirect } from "next/navigation";

import { authOptions } from "@/auth";

const memoryApiUrl = process.env.MEMORY_API_URL ?? "http://127.0.0.1:8000";

type MemoryRow = {
  id: string;
  content: string;
  memory_type: "episodic" | "semantic" | "procedural";
  session_id: string;
  created_at: string;
  last_accessed_at: string | null;
  access_count: number;
  importance: number;
  source_metadata: Record<string, unknown>;
};

const typeColor: Record<MemoryRow["memory_type"], string> = {
  episodic: "text-[#8B8B90] border-[#232326]",
  semantic: "text-[#7EE0C8] border-[#232326]",
  procedural: "text-[#FFB020] border-[#232326]",
};

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
  const query = new URLSearchParams();
  if (params.session_id) query.set("session_id", params.session_id);
  if (params.memory_type) query.set("memory_type", params.memory_type);
  if (params.q) query.set("q", params.q);
  const response = await fetch(`${memoryApiUrl}/memories?${query.toString()}`, {
    headers: { Authorization: `Bearer ${session.memoriaToken}` },
    cache: "no-store",
  });
  const payload = response.ok
    ? ((await response.json()) as { memories: MemoryRow[] })
    : { memories: [] };

  return (
    <div className="mx-auto flex min-h-full w-full max-w-5xl gap-10 px-8 py-10">
      <aside className="w-48 shrink-0 font-mono text-sm text-[#8B8B90]">
        <p className="text-[#F2F2F0]">Memoria</p>
        <nav className="mt-8 space-y-3">
          <p className="text-[#00E08F]">Memories</p>
          <Link href="/dashboard/keys">API Keys</Link>
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
        <h1 className="text-2xl font-semibold">Memories</h1>
        <form className="mt-6 flex flex-wrap gap-3 font-mono text-sm" method="get">
          <input
            className="rounded-md border border-[#232326] bg-black px-3 py-2"
            defaultValue={params.session_id ?? ""}
            name="session_id"
            placeholder="session_id"
          />
          <select
            className="rounded-md border border-[#232326] bg-black px-3 py-2"
            defaultValue={params.memory_type ?? ""}
            name="memory_type"
          >
            <option value="">all types</option>
            <option value="episodic">episodic</option>
            <option value="semantic">semantic</option>
            <option value="procedural">procedural</option>
          </select>
          <input
            className="rounded-md border border-[#232326] bg-black px-3 py-2"
            defaultValue={params.q ?? ""}
            name="q"
            placeholder="search content"
          />
          <button className="rounded-md bg-[#00E08F] px-3 py-2 text-black" type="submit">
            Filter
          </button>
        </form>
        <div className="mt-8 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="font-mono text-xs uppercase tracking-wider text-[#8B8B90]">
              <tr>
                <th className="pb-3">Content</th>
                <th className="pb-3">Type</th>
                <th className="pb-3">Session</th>
                <th className="pb-3">Created</th>
              </tr>
            </thead>
            <tbody>
              {payload.memories.map((memory) => (
                <tr className="border-t border-[#232326]" key={memory.id}>
                  <td className="max-w-md py-3 pr-4">
                    {memory.content.length > 120
                      ? `${memory.content.slice(0, 120)}…`
                      : memory.content}
                  </td>
                  <td className="py-3 pr-4">
                    <span
                      className={`rounded-full border px-2 py-1 font-mono text-xs ${typeColor[memory.memory_type]}`}
                    >
                      {memory.memory_type}
                    </span>
                  </td>
                  <td className="py-3 pr-4 font-mono text-xs text-[#8B8B90]">
                    {memory.session_id}
                  </td>
                  <td className="py-3 font-mono text-xs text-[#8B8B90]">
                    {memory.created_at.slice(0, 10)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {payload.memories.length === 0 ? (
            <p className="mt-6 font-mono text-sm text-[#8B8B90]">No memories yet.</p>
          ) : null}
        </div>
      </section>
    </div>
  );
}
