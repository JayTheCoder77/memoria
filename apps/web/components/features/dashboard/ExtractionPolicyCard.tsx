"use client";

import { useState } from "react";

import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import type { ExtractionPolicy } from "@/lib/api-client";

import { saveExtractionPolicy } from "./actions";

export function ExtractionPolicyCard({ policy }: { policy: ExtractionPolicy }) {
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [saved, setSaved] = useState(false);

  return (
    <Card className="p-6">
      <p className="font-mono text-xs uppercase tracking-[0.18em] text-text-secondary">
        Extraction
      </p>
      <p className="mt-3 text-sm text-text-secondary">
        Extra instructions are appended when memories are extracted. Categories outside
        this list are dropped.
      </p>
      <form
        className="mt-6 space-y-3"
        onSubmit={async (event) => {
          event.preventDefault();
          const form = event.currentTarget;
          const data = new FormData(form);
          const instructions = String(data.get("instructions") ?? "");
          const categories = String(data.get("categories") ?? "");
          setPending(true);
          setError(null);
          setSaved(false);
          try {
            await saveExtractionPolicy(instructions, categories);
            setSaved(true);
          } catch (err) {
            setError(err instanceof Error ? err.message : "Save failed");
          } finally {
            setPending(false);
          }
        }}
      >
        <label className="block">
          <span className="font-mono text-xs text-text-secondary">Instructions</span>
          <textarea
            className="mt-2 min-h-28 w-full border border-border-subtle bg-bg-terminal px-3 py-2 text-sm"
            defaultValue={policy.instructions ?? ""}
            name="instructions"
            placeholder="Ignore calendar small talk"
          />
        </label>
        <label className="block">
          <span className="font-mono text-xs text-text-secondary">Categories</span>
          <input
            className="mt-2 w-full border border-border-subtle bg-bg-terminal px-3 py-2 font-mono text-sm"
            defaultValue={policy.categories.join(", ")}
            name="categories"
            placeholder="shipping, billing"
          />
        </label>
        <Button disabled={pending} type="submit">
          Save extraction policy
        </Button>
      </form>
      {saved ? <p className="mt-3 text-sm text-accent">Saved.</p> : null}
      {error ? <p className="mt-3 text-sm text-danger">{error}</p> : null}
    </Card>
  );
}
