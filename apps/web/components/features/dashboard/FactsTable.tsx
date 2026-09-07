"use client";

import type { KvFactRow } from "@/lib/api-client";

export function FactsTable({ facts }: { facts: KvFactRow[] }) {
  return (
    <div className="mt-2 overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="font-mono text-xs uppercase tracking-wider text-text-secondary">
          <tr>
            <th className="pb-3">Type</th>
            <th className="pb-3">Entity</th>
            <th className="pb-3">Value</th>
            <th className="pb-3">Memory</th>
          </tr>
        </thead>
        <tbody>
          {facts.map((fact) => (
            <tr
              className="border-t border-border-subtle"
              key={`${fact.fact_type}:${fact.entity}`}
            >
              <td className="py-3 pr-4 font-mono text-xs">{fact.fact_type}</td>
              <td className="py-3 pr-4">{fact.entity}</td>
              <td className="py-3 pr-4 text-text-secondary">{fact.value ?? "—"}</td>
              <td className="py-3 font-mono text-xs text-text-secondary">
                {fact.memory_id.slice(0, 8)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {facts.length === 0 ? (
        <p className="mt-6 font-mono text-sm text-text-secondary">No KV facts yet.</p>
      ) : null}
    </div>
  );
}
