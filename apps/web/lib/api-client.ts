const memoryApiUrl = process.env.MEMORY_API_URL ?? "http://127.0.0.1:8000";

export type ApiKeyRow = {
  id: string;
  key_last4: string;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
};

export type MemoryRow = {
  id: string;
  content: string;
  memory_type: "episodic" | "semantic" | "procedural";
  session_id: string;
  created_at: string;
  last_accessed_at: string | null;
  access_count: number;
  importance: number;
  source_metadata: Record<string, unknown>;
};

export type MeResponse = {
  user: { id: string; org_id: string; email: string; name: string; google_id: string };
  org: { id: string; name: string };
};

async function apiFetch(path: string, token: string, init?: RequestInit) {
  return fetch(`${memoryApiUrl}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
}

export async function listApiKeys(token: string): Promise<ApiKeyRow[]> {
  const response = await apiFetch("/api-keys", token);
  if (!response.ok) return [];
  const payload = (await response.json()) as { keys: ApiKeyRow[] };
  return payload.keys;
}

export async function listMemories(
  token: string,
  params: { session_id?: string; memory_type?: string; q?: string } = {},
): Promise<MemoryRow[]> {
  const query = new URLSearchParams();
  if (params.session_id) query.set("session_id", params.session_id);
  if (params.memory_type) query.set("memory_type", params.memory_type);
  if (params.q) query.set("q", params.q);
  const suffix = query.toString() ? `?${query.toString()}` : "";
  const response = await apiFetch(`/memories${suffix}`, token);
  if (!response.ok) return [];
  const payload = (await response.json()) as { memories: MemoryRow[] };
  return payload.memories;
}

export async function getMe(token: string): Promise<MeResponse | null> {
  const response = await apiFetch("/auth/me", token);
  if (!response.ok) return null;
  return (await response.json()) as MeResponse;
}

export async function createApiKeyRequest(token: string) {
  const response = await apiFetch("/api-keys", token, { method: "POST" });
  if (!response.ok) {
    throw new Error("Could not create API key");
  }
  return (await response.json()) as { key: string; key_last4: string };
}

export async function revokeApiKeyRequest(token: string, keyId: string) {
  const response = await apiFetch(`/api-keys/${keyId}`, token, { method: "DELETE" });
  if (!response.ok) {
    throw new Error("Could not revoke API key");
  }
}
