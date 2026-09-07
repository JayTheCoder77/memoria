"use client";

import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import type { GroqStatus } from "@/lib/api-client";

import { clearGroq, saveGroq } from "./actions";

export function GroqCard({ status }: { status: GroqStatus }) {
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [saved, setSaved] = useState(false);

  return (
    <Card className="p-6">
      <p className="font-mono text-xs uppercase tracking-[0.18em] text-text-secondary">
        Groq · BYOK
      </p>
      <p className="mt-3 text-sm text-text-secondary">
        Used when OpenRouter is missing or fails. Model is fixed to llama-3.1-8b-instant.
        Raw key encrypted; last 4 only.
      </p>
      <p className="mt-2 font-mono text-xs text-text-secondary">
        {status.configured ? `configured · …${status.last4}` : "not configured"}
      </p>
      <form
        className="mt-6 space-y-3"
        onSubmit={async (event) => {
          event.preventDefault();
          const form = event.currentTarget;
          const data = new FormData(form);
          const apiKey = String(data.get("api_key") ?? "");
          setPending(true);
          setError(null);
          setSaved(false);
          try {
            await saveGroq(apiKey);
            form.reset();
            setSaved(true);
          } catch (err) {
            setError(err instanceof Error ? err.message : "Save failed");
          } finally {
            setPending(false);
          }
        }}
      >
        <label className="block">
          <span className="font-mono text-xs text-text-secondary">API key</span>
          <input
            className="mt-2 w-full border border-border-subtle bg-bg-terminal px-3 py-2 font-mono text-sm"
            name="api_key"
            placeholder="gsk_…"
            required
            type="password"
            autoComplete="off"
          />
        </label>
        <div className="flex flex-wrap gap-3">
          <Button disabled={pending} type="submit">
            Save key
          </Button>
          {status.configured ? (
            <Button
              disabled={pending}
              type="button"
              variant="ghost"
              onClick={async () => {
                setPending(true);
                setError(null);
                try {
                  await clearGroq();
                } catch (err) {
                  setError(err instanceof Error ? err.message : "Clear failed");
                } finally {
                  setPending(false);
                }
              }}
            >
              Remove key
            </Button>
          ) : null}
        </div>
      </form>
      {saved ? <p className="mt-3 text-sm text-accent">Saved.</p> : null}
      {error ? <p className="mt-3 text-sm text-danger">{error}</p> : null}
    </Card>
  );
}
