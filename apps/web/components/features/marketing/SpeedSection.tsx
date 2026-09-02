import { AnsiBar } from "@/components/ui/AnsiBar";
import { StatGrid } from "@/components/ui/StatGrid";

export function SpeedSection() {
  return (
    <section className="border-t border-border-subtle">
      <StatGrid
        stats={[
          { label: "Latency", value: "<100ms", hint: "p95 cached recall target" },
          { label: "MCP", value: "Stateless", hint: "Horizontally scalable adapter" },
          { label: "Types", value: "3", hint: "Episodic / semantic / procedural" },
          { label: "Isolation", value: "100%", hint: "Tenant-scoped at query time" },
        ]}
      />
      <div className="space-y-3 px-6 py-10 md:px-10">
        <AnsiBar filled={28} label="cached recall" />
        <AnsiBar filled={86} label="uncached vector search" />
      </div>
    </section>
  );
}
