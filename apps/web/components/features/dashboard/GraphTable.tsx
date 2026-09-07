"use client";

import { Badge } from "@/components/ui/Badge";
import type { GraphEdgeRow } from "@/lib/api-client";

export function GraphTable({
  edges,
  showInvalid,
}: {
  edges: GraphEdgeRow[];
  showInvalid: boolean;
}) {
  return (
    <div>
      <form className="flex flex-wrap gap-3 font-mono text-sm" method="get">
        <label className="flex items-center gap-2 text-text-secondary">
          <input defaultChecked={showInvalid} name="history" type="checkbox" value="1" />
          include invalidated
        </label>
        <button className="btn-cut bg-accent px-3 py-2 text-bg-terminal" type="submit">
          Filter
        </button>
      </form>
      <div className="mt-8 overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="font-mono text-xs uppercase tracking-wider text-text-secondary">
            <tr>
              <th className="pb-3">Subject</th>
              <th className="pb-3">Relation</th>
              <th className="pb-3">Object</th>
              <th className="pb-3">Status</th>
              <th className="pb-3">Confidence</th>
            </tr>
          </thead>
          <tbody>
            {edges.map((edge) => (
              <tr
                className="border-t border-border-subtle"
                key={`${edge.subject}:${edge.relation}:${edge.object}:${edge.valid_from}`}
              >
                <td className="py-3 pr-4">{edge.subject}</td>
                <td className="py-3 pr-4 font-mono text-xs">{edge.relation}</td>
                <td className="py-3 pr-4">{edge.object}</td>
                <td className="py-3 pr-4">
                  <Badge tone={edge.valid ? "accent" : "muted"}>
                    {edge.valid ? "valid" : "invalid"}
                  </Badge>
                </td>
                <td className="py-3 font-mono text-xs text-text-secondary">
                  {edge.confidence}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {edges.length === 0 ? (
          <p className="mt-6 font-mono text-sm text-text-secondary">No graph edges yet.</p>
        ) : null}
      </div>
    </div>
  );
}
