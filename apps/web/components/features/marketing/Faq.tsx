"use client";

import { useState } from "react";

import { SectionLabel } from "@/components/ui/SectionLabel";

const faqs = [
  {
    q: "Is this hosted or self-hosted?",
    a: "Both. The Memory API and MCP server run locally via Docker today. A hosted environment is the launch target; self-host remains first-class.",
  },
  {
    q: "What does it cost?",
    a: "MVP is free while we dogfood. There is no credit card required to get an API key.",
  },
  {
    q: "Which harnesses work?",
    a: "Any MCP client. We document Cursor and Claude Code first. LangGraph and custom agents use the same tools.",
  },
  {
    q: "How is data isolated?",
    a: "Every query is scoped to org_id from the API key or session JWT. Memories never leak across tenants.",
  },
  {
    q: "How long do memories live?",
    a: "Until you forget them. There is no automatic expiry in MVP. Consolidation merges near-duplicates instead of deleting history.",
  },
  {
    q: "Google OAuth vs API keys?",
    a: "Google is for humans on the dashboard. API keys are for machines. The MCP server never stores a user session.",
  },
];

export function Faq() {
  const [open, setOpen] = useState<number | null>(0);
  return (
    <section className="border-t border-border-subtle px-6 py-24 md:px-10">
      <div className="mx-auto max-w-3xl">
        <SectionLabel>FAQ</SectionLabel>
        <h2 className="mt-6 text-4xl font-semibold">Answers, numbered.</h2>
        <div className="mt-10 divide-y divide-border-subtle border-y border-border-subtle">
          {faqs.map((item, index) => {
            const n = String(index + 1).padStart(2, "0");
            const expanded = open === index;
            return (
              <button
                className="w-full py-5 text-left"
                key={item.q}
                type="button"
                onClick={() => setOpen(expanded ? null : index)}
              >
                <div className="flex items-baseline gap-4">
                  <span className="font-mono text-xs text-accent">{n}</span>
                  <span className="text-lg font-medium">{item.q}</span>
                </div>
                {expanded ? (
                  <p className="mt-3 pl-8 text-sm leading-6 text-text-secondary">{item.a}</p>
                ) : null}
              </button>
            );
          })}
        </div>
      </div>
    </section>
  );
}
