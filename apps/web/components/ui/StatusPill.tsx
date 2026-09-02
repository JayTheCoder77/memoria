type Status = "operational" | "active" | "revoked" | "secure";

const copy: Record<Status, { label: string; className: string }> = {
  operational: { label: "Operational", className: "text-accent" },
  active: { label: "Active", className: "text-accent" },
  revoked: { label: "Revoked", className: "text-danger" },
  secure: { label: "Secure via Google OAuth", className: "text-text-secondary" },
};

export function StatusPill({
  status = "operational",
  label,
}: {
  status?: Status;
  label?: string;
}) {
  const item = copy[status];
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full border border-border-subtle px-3 py-1 font-mono text-xs ${item.className}`}
    >
      <span aria-hidden>●</span>
      {label ?? item.label}
    </span>
  );
}
