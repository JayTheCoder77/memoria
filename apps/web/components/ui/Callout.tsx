import type { ReactNode } from "react";

const tones = {
  note: "border-accent text-accent",
  warning: "border-warning text-warning",
  danger: "border-danger text-danger",
};

export function Callout({
  tone = "note",
  children,
}: {
  tone?: keyof typeof tones;
  children: ReactNode;
}) {
  const label = tone === "note" ? "NOTE" : tone.toUpperCase();
  return (
    <div className={`border-l-2 bg-bg-raised px-4 py-3 ${tones[tone]}`}>
      <p className="font-mono text-xs">{label}</p>
      <div className="mt-2 text-sm text-text-primary">{children}</div>
    </div>
  );
}
