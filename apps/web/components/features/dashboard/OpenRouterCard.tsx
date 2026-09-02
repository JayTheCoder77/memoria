"use client";

import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import type { OpenRouterStatus } from "@/lib/api-client";

import { clearOpenRouter, saveOpenRouter } from "./actions";

export function OpenRouterCard({ status }: { status: OpenRouterStatus }) {
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [saved, setSaved] = useState(false);

  return (
    <Card className="p-6">
      <p className="font-mono text-xs uppercase tracking-[0.18em] text-text-secondary">
        OpenRouter · BYOK
      </p>
      <p className="mt-3 text-sm text-text-secondary">
        Extraction uses your OpenRouter key. Memoria never uses a shared LLM key. The
        raw key is stored encrypted and shown as last 4 only.
      </p>
      <p className="mt-2 font-mono text-xs text-text-secondary">
        {status.configured ? `configured · …${status.last4}` : "not configured · heuristic fallback"}
      </p>
      <form
        className="mt-6 space-y-3"
        onSubmit={async (event) => {
          event.preventDefault();
          const form = event.currentTarget;
          const data = new FormData(form);
          const apiKey = String(data.get("api_key") ?? "");
          const model = String(data.get("model") ?? "");
          setPending(true);
          setError(null);
          setSaved(false);
          try {
            await saveOpenRouter(apiKey, model);
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
            placeholder="sk-or-v1-…"
            required
            type="password"
            autoComplete="off"
          />
        </label>
        <label className="block">
          <span className="font-mono text-xs text-text-secondary">Model</span>
          <input
            className="mt-2 w-full border border-border-subtle bg-bg-terminal px-3 py-2 font-mono text-sm"
            defaultValue={status.model ?? "openai/gpt-4o-mini"}
            name="model"
            placeholder="openai/gpt-4o-mini"
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
                  await clearOpenRouter();
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
