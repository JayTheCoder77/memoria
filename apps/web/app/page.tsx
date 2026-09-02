import Link from "next/link";

export default function Home() {
  return (
    <main className="flex min-h-full flex-1 flex-col items-center justify-center px-6 text-center">
      <p className="font-mono text-xs uppercase tracking-[0.2em] text-[#8B8B90]">
        Memoria
      </p>
      <h1 className="mt-4 max-w-xl text-4xl font-semibold">
        Agentic memory for MCP harnesses
      </h1>
      <p className="mt-4 max-w-lg text-[#8B8B90]">
        Sign in to manage org API keys, then plug them into Cursor or Claude Code.
      </p>
      <Link
        href="/login"
        className="mt-8 rounded-md bg-[#00E08F] px-5 py-3 font-medium text-black"
      >
        Sign in
      </Link>
    </main>
  );
}
