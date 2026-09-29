import { afterEach, expect, test } from "bun:test";

import { getExtractionPolicy } from "./api-client";

const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
});

test("failed extraction policy load is not an empty policy", async () => {
  globalThis.fetch = async () => new Response("unavailable", { status: 503 });

  const result = await getExtractionPolicy("session-token");

  expect(result).toEqual({
    ok: false,
    error: "Could not load extraction policy",
  });
});
