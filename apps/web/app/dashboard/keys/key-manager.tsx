"use client";

import { useState } from "react";

import { createApiKey, revokeApiKey } from "./actions";

type KeyRow = {
  id: string;
  key_last4: string;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
};

export function KeyManager({ keys }: { keys: KeyRow[] }) {
  const [plaintext, setPlaintext] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">API Keys</h1>
        <button
          className="rounded-md bg-[#00E08F] px-3 py-2 font-mono text-sm text-black"
          type="button"
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
        </button>
      </div>
      {plaintext ? (
        <div className="rounded-lg border border-[#FFB020] bg-black p-4 font-mono text-sm">
          <p className="text-[#FFB020]">Shown once — copy it now.</p>
          <p className="mt-2 break-all text-[#F2F2F0]">{plaintext}</p>
        </div>
      ) : null}
      {error ? <p className="text-sm text-[#FF5C5C]">{error}</p> : null}
      <table className="w-full text-left text-sm">
        <thead className="font-mono text-xs uppercase text-[#8B8B90]">
          <tr>
            <th className="py-2">Key</th>
            <th>Created</th>
            <th>Last used</th>
            <th>Status</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {keys.map((key) => (
            <tr key={key.id} className="border-t border-[#232326]">
              <td className="py-3 font-mono">mem_...{key.key_last4}</td>
              <td>{new Date(key.created_at).toLocaleDateString()}</td>
              <td>
                {key.last_used_at
                  ? new Date(key.last_used_at).toLocaleDateString()
                  : "—"}
              </td>
              <td>
                {key.revoked_at ? (
                  <span className="text-[#FF5C5C]">● Revoked</span>
                ) : (
                  <span className="text-[#00E08F]">● Active</span>
                )}
              </td>
              <td>
                {key.revoked_at ? null : (
                  <button
                    className="text-[#FF5C5C]"
                    type="button"
                    onClick={async () => {
                      if (!confirm("Revoke this key?")) {
                        return;
                      }
                      await revokeApiKey(key.id);
                    }}
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
