import { TerminalPanel } from "@/components/ui/TerminalPanel";
import type { MemoryRow } from "@/lib/api-client";

export function ActivityLog({ memories }: { memories: MemoryRow[] }) {
  const lines = [...memories]
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
    .slice(0, 12);

  return (
    <TerminalPanel title="activity · memories">
      {lines.length === 0 ? (
        <p className="text-text-secondary">No activity yet. remember() or emit() to start.</p>
      ) : (
        lines.map((memory) => (
          <p key={memory.id}>
            <span className="text-text-secondary">
              {memory.created_at.replace("T", " ").slice(0, 19)}
            </span>{" "}
            <span className="text-accent">remember</span> {memory.memory_type} ·{" "}
            {memory.content.length > 72 ? `${memory.content.slice(0, 72)}…` : memory.content}
          </p>
        ))
      )}
    </TerminalPanel>
  );
}
