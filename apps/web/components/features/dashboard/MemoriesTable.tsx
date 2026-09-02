"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { CodeBlock } from "@/components/ui/CodeBlock";
import type { MemoryRow } from "@/lib/api-client";

const typeTone = {
  episodic: "episodic",
  semantic: "semantic",
  procedural: "procedural",
} as const;

export function MemoriesTable({
  memories,
  filters,
}: {
  memories: MemoryRow[];
  filters: { session_id?: string; memory_type?: string; q?: string };
}) {
  const [open, setOpen] = useState<MemoryRow | null>(null);

  return (
    <div>
      <form className="flex flex-wrap gap-3 font-mono text-sm" method="get">
        <input
          className="rounded-md border border-border-subtle bg-bg-terminal px-3 py-2"
          defaultValue={filters.session_id ?? ""}
          name="session_id"
          placeholder="session_id"
        />
        <select
          className="rounded-md border border-border-subtle bg-bg-terminal px-3 py-2"
          defaultValue={filters.memory_type ?? ""}
          name="memory_type"
        >
          <option value="">all types</option>
          <option value="episodic">episodic</option>
          <option value="semantic">semantic</option>
          <option value="procedural">procedural</option>
        </select>
        <input
          className="rounded-md border border-border-subtle bg-bg-terminal px-3 py-2"
          defaultValue={filters.q ?? ""}
          name="q"
          placeholder="search content"
        />
        <button className="btn-cut bg-accent px-3 py-2 text-bg-terminal" type="submit">
          Filter
        </button>
      </form>
      <div className="mt-8 overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="font-mono text-xs uppercase tracking-wider text-text-secondary">
            <tr>
              <th className="pb-3">Content</th>
              <th className="pb-3">Type</th>
              <th className="pb-3">Session</th>
              <th className="pb-3">Created</th>
              <th className="pb-3">Last accessed</th>
            </tr>
          </thead>
          <tbody>
            {memories.map((memory) => (
              <tr
                className="cursor-pointer border-t border-border-subtle hover:bg-bg-raised"
                key={memory.id}
                onClick={() => setOpen(memory)}
              >
                <td className="max-w-md py-3 pr-4">
                  {memory.content.length > 120
                    ? `${memory.content.slice(0, 120)}…`
                    : memory.content}
                </td>
                <td className="py-3 pr-4">
                  <Badge tone={typeTone[memory.memory_type]}>{memory.memory_type}</Badge>
                </td>
                <td className="py-3 pr-4 font-mono text-xs text-text-secondary">
                  {memory.session_id}
                </td>
                <td className="py-3 font-mono text-xs text-text-secondary">
                  {memory.created_at.slice(0, 10)}
                </td>
                <td className="py-3 font-mono text-xs text-text-secondary">
                  {memory.last_accessed_at?.slice(0, 10) ?? "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {memories.length === 0 ? (
          <p className="mt-6 font-mono text-sm text-text-secondary">No memories yet.</p>
        ) : null}
      </div>
      {open ? (
        <div className="fixed inset-0 z-20 flex justify-end bg-bg-terminal/60">
          <aside className="h-full w-full max-w-lg overflow-y-auto border-l border-border-subtle bg-bg-base p-6">
            <div className="flex items-start justify-between gap-4">
              <div>
                <Badge tone={typeTone[open.memory_type]}>{open.memory_type}</Badge>
                <p className="mt-3 font-mono text-xs text-text-secondary">{open.session_id}</p>
              </div>
              <button
                className="font-mono text-xs text-text-secondary"
                type="button"
                onClick={() => setOpen(null)}
              >
                Close
              </button>
            </div>
            <p className="mt-6 text-sm leading-6">{open.content}</p>
            <dl className="mt-6 grid grid-cols-2 gap-4 font-mono text-xs text-text-secondary">
              <div>
                <dt>access_count</dt>
                <dd className="mt-1 text-text-primary">{open.access_count}</dd>
              </div>
              <div>
                <dt>importance</dt>
                <dd className="mt-1 text-text-primary">{open.importance}</dd>
              </div>
            </dl>
            <div className="mt-6">
              <p className="mb-2 font-mono text-xs text-text-secondary">source_metadata</p>
              <CodeBlock
                code={JSON.stringify(open.source_metadata, null, 2)}
                language="json"
              />
            </div>
          </aside>
        </div>
      ) : null}
    </div>
  );
}
