"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { StatusPill } from "@/components/ui/StatusPill";
import { TerminalPanel } from "@/components/ui/TerminalPanel";
import type { ApiKeyRow } from "@/lib/api-client";

import { createApiKey, revokeApiKey } from "./actions";

export function ApiKeysList({ keys }: { keys: ApiKeyRow[] }) {
  const [plaintext, setPlaintext] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<string | null>(null);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <p className="text-sm text-text-secondary">
          Keys are shown in full once. Store them in the harness MCP config.
        </p>
        <Button
          onClick={async () => {
            try {
              const created = await createApiKey();
              setPlaintext(created.key);
              setError(null);
            } catch (err) {
              setError(err instanceof Error ? err.message : "Create failed");
            }
          }}
        >
          Create new key
        </Button>
      </div>
      {plaintext ? (
        <TerminalPanel title="new key · shown once">
          <p className="text-warning">Won&apos;t be shown again. Copy it now.</p>
          <p className="mt-2 break-all">{plaintext}</p>
          <button
            className="mt-3 text-xs text-accent"
            type="button"
            onClick={() => navigator.clipboard.writeText(plaintext)}
          >
            Copy
          </button>
        </TerminalPanel>
      ) : null}
      {error ? <p className="text-sm text-danger">{error}</p> : null}
      <table className="w-full text-left text-sm">
        <thead className="font-mono text-xs uppercase tracking-wider text-text-secondary">
          <tr>
            <th className="pb-3">Key</th>
            <th className="pb-3">Created</th>
            <th className="pb-3">Last used</th>
            <th className="pb-3">Status</th>
            <th className="pb-3" />
          </tr>
        </thead>
        <tbody>
          {keys.map((key) => (
            <tr className="border-t border-border-subtle" key={key.id}>
              <td className="py-3 font-mono">mem_...{key.key_last4}</td>
              <td>{key.created_at.slice(0, 10)}</td>
              <td>{key.last_used_at?.slice(0, 10) ?? "—"}</td>
              <td>
                {key.revoked_at ? (
                  <StatusPill status="revoked" />
                ) : (
                  <StatusPill status="active" />
                )}
              </td>
              <td>
                {key.revoked_at ? (
                  <Badge>revoked</Badge>
                ) : pending === key.id ? (
                  <div className="flex gap-2">
                    <Button
                      className="h-8 px-3 text-xs"
                      variant="danger"
                      onClick={async () => {
                        await revokeApiKey(key.id);
                        setPending(null);
                      }}
                    >
                      Confirm
                    </Button>
                    <Button
                      className="h-8 px-3 text-xs"
                      variant="ghost"
                      onClick={() => setPending(null)}
                    >
                      Cancel
                    </Button>
                  </div>
                ) : (
                  <button
                    className="text-danger"
                    type="button"
                    onClick={() => setPending(key.id)}
                  >
                    Revoke
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
