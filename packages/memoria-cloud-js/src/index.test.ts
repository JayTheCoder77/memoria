import { afterEach, describe, expect, test } from "bun:test";
import {
  Memoria,
  MemoriaAuthError,
  MemoriaNotFoundError,
  MemoriaRateLimitError,
} from "./index.ts";

function memoryJson(overrides: Record<string, unknown> = {}) {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    org_id: "22222222-2222-2222-2222-222222222222",
    session_id: "s1",
    memory_type: "semantic",
    content: "remember this",
    importance: 0.5,
    access_count: 0,
    source_metadata: {},
    created_at: "2026-09-02T00:00:00+00:00",
    updated_at: null,
    last_accessed_at: null,
    score: null,
    ...overrides,
  };
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("Memoria", () => {
  afterEach(() => {
    delete process.env.MEMORY_API_KEY;
    delete process.env.MEMORY_API_URL;
  });

  test("remember posts to the memory API", async () => {
    const seen: Request[] = [];
    const client = new Memoria({
      apiKey: "mem_testkey",
      baseUrl: "http://memory",
      fetch: async (input, init) => {
        const request = new Request(input, init);
        seen.push(request);
        expect(request.headers.get("authorization")).toBe("Bearer mem_testkey");
        return jsonResponse(201, memoryJson());
      },
    });
    const memory = await client.remember({ content: "remember this", session_id: "s1" });
    expect(memory.content).toBe("remember this");
    expect(seen[0]?.method).toBe("POST");
    expect(new URL(seen[0]!.url).pathname).toBe("/memories");
  });

  test("recall update forget emit and inspect call expected routes", async () => {
    const seen: Request[] = [];
    const memoryId = "11111111-1111-1111-1111-111111111111";
    const client = new Memoria({
      apiKey: "mem_testkey",
      baseUrl: "http://memory",
      fetch: async (input, init) => {
        const request = new Request(input, init);
        seen.push(request);
        const path = new URL(request.url).pathname;
        if (request.method === "GET" && path === "/memories/search") {
          return jsonResponse(200, { memories: [] });
        }
        if (request.method === "GET" && path === "/memories") {
          return jsonResponse(200, { memories: [] });
        }
        if (request.method === "GET" && path === "/kv-facts") {
          return jsonResponse(200, { facts: [] });
        }
        if (request.method === "GET" && path === "/graph-edges") {
          return jsonResponse(200, { edges: [] });
        }
        if (request.method === "GET" && path === "/health") {
          return jsonResponse(200, { status: "ok" });
        }
        if (request.method === "PATCH") {
          return jsonResponse(200, memoryJson({ id: memoryId, content: "updated" }));
        }
        if (request.method === "DELETE") {
          return new Response(null, { status: 204 });
        }
        if (request.method === "POST" && path === "/events") {
          return jsonResponse(202, { status: "queued", id: memoryId });
        }
        return jsonResponse(404, { detail: "not found" });
      },
    });

    await client.recall({ q: "org wide" });
    expect(new URL(seen[0]!.url).searchParams.has("session_id")).toBe(false);
    await client.recall({ q: "remember this", session_id: "s1" });
    expect(new URL(seen[1]!.url).searchParams.get("session_id")).toBe("s1");
    await client.recall({ q: "history", as_of: "2026-03-01T00:00:00Z" });
    expect(new URL(seen[2]!.url).searchParams.get("as_of")).toBe("2026-03-01T00:00:00Z");
    await client.recall({ q: "why", explain: true });
    expect(new URL(seen[3]!.url).searchParams.get("explain")).toBe("true");
    await client.update(memoryId, { content: "updated" });
    await client.forget(memoryId);
    const emitted = await client.emit({
      session_id: "s1",
      event_type: "message",
      payload: { content: "We prefer pytest" },
    });
    expect(emitted.status).toBe("queued");
    await client.listMemories({ session_id: "s1", memory_type: "semantic", q: "prefer" });
    await client.kvFacts({ limit: 10, offset: 5 });
    await client.graphEdges({ valid_only: false });
    const health = await client.health();
    expect(health.status).toBe("ok");
    expect(seen.map((item) => [item.method, new URL(item.url).pathname])).toEqual([
      ["GET", "/memories/search"],
      ["GET", "/memories/search"],
      ["GET", "/memories/search"],
      ["GET", "/memories/search"],
      ["PATCH", `/memories/${memoryId}`],
      ["DELETE", `/memories/${memoryId}`],
      ["POST", "/events"],
      ["GET", "/memories"],
      ["GET", "/kv-facts"],
      ["GET", "/graph-edges"],
      ["GET", "/health"],
    ]);
    expect(new URL(seen[8]!.url).searchParams.get("limit")).toBe("10");
    expect(new URL(seen[8]!.url).searchParams.get("offset")).toBe("5");
    expect(new URL(seen[9]!.url).searchParams.get("valid_only")).toBe("false");
  });

  test("reads the default base URL and env key", async () => {
    process.env.MEMORY_API_KEY = "mem_from_env";
    delete process.env.MEMORY_API_URL;
    const client = new Memoria({
      fetch: async (input, init) => {
        const request = new Request(input, init);
        expect(request.headers.get("authorization")).toBe("Bearer mem_from_env");
        return jsonResponse(200, { status: "ok" });
      },
    });
    expect(client.baseUrl).toBe("https://memoria-api-jw5g.onrender.com");
    expect((await client.health()).status).toBe("ok");
  });

  test("maps status errors", async () => {
    const unauthorized = new Memoria({
      apiKey: "mem_x",
      baseUrl: "http://memory",
      fetch: async () => jsonResponse(401, { detail: "Invalid or missing API key" }),
    });
    const missing = new Memoria({
      apiKey: "mem_x",
      baseUrl: "http://memory",
      fetch: async () => jsonResponse(404, { detail: "Memory not found" }),
    });
    const limited = new Memoria({
      apiKey: "mem_x",
      baseUrl: "http://memory",
      fetch: async () => jsonResponse(429, { detail: "Rate limit exceeded" }),
    });
    await expect(unauthorized.recall({ q: "nope" })).rejects.toBeInstanceOf(MemoriaAuthError);
    await expect(missing.forget("abc")).rejects.toBeInstanceOf(MemoriaNotFoundError);
    await expect(limited.recall({ q: "too many" })).rejects.toBeInstanceOf(MemoriaRateLimitError);
  });

  test("missing api key raises", async () => {
    delete process.env.MEMORY_API_KEY;
    const client = new Memoria({
      baseUrl: "http://memory",
      fetch: async () => jsonResponse(200, { memories: [] }),
    });
    await expect(client.recall({ q: "no key" })).rejects.toBeInstanceOf(MemoriaAuthError);
  });
});
