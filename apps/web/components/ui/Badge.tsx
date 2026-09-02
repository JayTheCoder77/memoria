import type { ReactNode } from "react";

type Tone = "muted" | "accent" | "episodic" | "semantic" | "procedural";

const tones: Record<Tone, string> = {
  muted: "border-border-subtle text-text-secondary",
  accent: "border-border-subtle text-accent",
  episodic: "border-border-subtle text-type-episodic",
  semantic: "border-border-subtle text-type-semantic",
  procedural: "border-border-subtle text-type-procedural",
};

export function Badge({
  children,
  tone = "muted",
}: {
  children: ReactNode;
  tone?: Tone;
}) {
  return (
    <span
      className={`inline-flex rounded-full border px-2 py-1 font-mono text-xs ${tones[tone]}`}
    >
      {children}
    </span>
  );
}
