"use client";

import { useState } from "react";

export function CodeBlock({
  code,
  language = "json",
}: {
  code: string;
  language?: string;
}) {
  const [copied, setCopied] = useState(false);

  return (
    <div className="overflow-hidden border border-border-subtle bg-bg-terminal">
      <div className="flex items-center justify-between border-b border-border-subtle px-4 py-2">
        <p className="font-mono text-xs text-text-secondary">{language}</p>
        <button
          className="font-mono text-xs text-accent"
          type="button"
          onClick={async () => {
            await navigator.clipboard.writeText(code);
            setCopied(true);
            window.setTimeout(() => setCopied(false), 1500);
          }}
        >
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre className="overflow-x-auto p-4 font-mono text-sm leading-6 text-text-primary">
        <code>{code}</code>
      </pre>
    </div>
  );
}
