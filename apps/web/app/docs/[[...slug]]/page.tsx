import { notFound } from "next/navigation";

import { docsPages } from "@/lib/docs";
import { mcpConfigSnippet } from "@/lib/mcp-config";

export default async function DocsPage({
  params,
}: {
  params: Promise<{ slug?: string[] }>;
}) {
  const { slug } = await params;
  const key = slug?.[0] ?? "quickstart";
  const pages = docsPages(mcpConfigSnippet);
  const page = pages[key];
  if (!page) {
    notFound();
  }

  return (
    <div className="flex">
      <article className="prose-docs mx-auto max-w-[720px] flex-1 px-8 py-10">
        <p className="font-mono text-xs uppercase tracking-[0.18em] text-accent">
          {page.section}
        </p>
        <h1 className="mt-3 text-4xl font-semibold">{page.title}</h1>
        <div className="docs-body mt-8 space-y-6 text-[15px] leading-7 text-text-primary">
          {page.body}
        </div>
      </article>
      <nav className="hidden w-48 shrink-0 px-6 py-10 lg:block">
        <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-text-secondary">
          On this page
        </p>
        <div className="mt-4 space-y-2 font-mono text-xs text-text-secondary">
          {page.headings.map((heading) => (
            <a className="block" href={`#${heading.id}`} key={heading.id}>
              {heading.label}
            </a>
          ))}
        </div>
      </nav>
    </div>
  );
}
