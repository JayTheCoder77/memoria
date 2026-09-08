export const DEFAULT_BASE_URL = "https://memoria-api-jw5g.onrender.com";

export class MemoriaError extends Error {
  readonly statusCode: number | undefined;

  constructor(message: string, statusCode?: number) {
    super(message);
    this.name = "MemoriaError";
    this.statusCode = statusCode;
  }
}

export class MemoriaAuthError extends MemoriaError {
  constructor(message: string, statusCode?: number) {
    super(message, statusCode);
    this.name = "MemoriaAuthError";
  }
}

export class MemoriaNotFoundError extends MemoriaError {
  constructor(message: string, statusCode?: number) {
    super(message, statusCode);
    this.name = "MemoriaNotFoundError";
  }
}

export class MemoriaRateLimitError extends MemoriaError {
  constructor(message: string, statusCode?: number) {
    super(message, statusCode);
    this.name = "MemoriaRateLimitError";
  }
}

export type ScoreDetails = {
  relevance: number;
  importance: number;
  recency: number;
  sources: string[];
  vector_similarity: number;
  kv_match: number | null;
  graph_hops: number | null;
  weights: Record<string, number>;
};

export type Memory = {
  id: string;
  org_id: string;
  session_id: string;
  memory_type: string;
  content: string;
  importance: number;
  access_count: number;
  source_metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string | null;
  last_accessed_at: string | null;
  score: number | null;
  score_details?: ScoreDetails | null;
};

export type MemorySearchResult = {
  memories: Memory[];
  timings_ms?: Record<string, number> | null;
};

export type KvFact = {
  fact_type: string;
  entity: string;
  value: string | null;
  memory_id: string;
  importance: number;
};

export type GraphEdge = {
  subject: string;
  relation: string;
  object: string;
  valid: boolean;
  valid_from: string | null;
  valid_to: string | null;
  confidence: number;
  memory_id: string | null;
};

export type EmitResult = {
  status: "queued" | "skipped";
  id?: string | null;
};

export type MemoriaOptions = {
  apiKey?: string;
  baseUrl?: string;
  fetch?: typeof fetch;
};

export class Memoria {
  readonly baseUrl: string;
  private readonly apiKey: string | undefined;
  private readonly fetchImpl: typeof fetch;

  constructor(options: MemoriaOptions = {}) {
    const envUrl = (process.env.MEMORY_API_URL ?? "").trim().replace(/\/$/, "");
    this.baseUrl = ((options.baseUrl ?? envUrl) || DEFAULT_BASE_URL).replace(/\/$/, "");
    this.apiKey = options.apiKey;
    this.fetchImpl = options.fetch ?? fetch;
  }

  private resolveKey(required: boolean): string {
    const raw = this.apiKey ?? process.env.MEMORY_API_KEY ?? "";
    const key = raw.trim();
    if (required && !key) {
      throw new MemoriaAuthError("MEMORY_API_KEY is not set");
    }
    return key;
  }

  private headers(required = true): Record<string, string> {
    const key = this.resolveKey(required);
    if (!key) {
      return {};
    }
    return { Authorization: `Bearer ${key}` };
  }

  private async request(
    method: string,
    path: string,
    options: {
      query?: Record<string, string | number | boolean | undefined>;
      body?: unknown;
      requireKey?: boolean;
    } = {},
  ): Promise<Response> {
    const url = new URL(path, `${this.baseUrl}/`);
    for (const [key, value] of Object.entries(options.query ?? {})) {
      if (value === undefined) {
        continue;
      }
      url.searchParams.set(key, String(value));
    }
    const headers: Record<string, string> = { ...this.headers(options.requireKey ?? true) };
    if (options.body !== undefined) {
      headers["Content-Type"] = "application/json";
    }
    return this.fetchImpl(url, {
      method,
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
  }

  private async parseError(response: Response): Promise<never> {
    let message = `Memory API ${response.status}`;
    try {
      const payload: unknown = await response.json();
      if (payload && typeof payload === "object" && "detail" in payload) {
        message = String((payload as { detail: unknown }).detail);
      }
    } catch {
      const text = (await response.text()).trim();
      if (text) {
        message = text;
      }
    }
    if (response.status === 401) {
      throw new MemoriaAuthError(message, response.status);
    }
    if (response.status === 404) {
      throw new MemoriaNotFoundError(message, response.status);
    }
    if (response.status === 429) {
      throw new MemoriaRateLimitError(message, response.status);
    }
    throw new MemoriaError(message, response.status);
  }

  private async json<T>(response: Response): Promise<T> {
    if (!response.ok) {
      await this.parseError(response);
    }
    return (await response.json()) as T;
  }

  async remember(input: {
    content: string;
    session_id: string;
    memory_type?: string;
    importance?: number;
    source_metadata?: Record<string, unknown>;
    kv_triples?: Record<string, unknown>[];
    graph_triples?: Record<string, unknown>[];
  }): Promise<Memory> {
    const response = await this.request("POST", "/memories", {
      body: {
        session_id: input.session_id,
        memory_type: input.memory_type ?? "semantic",
        content: input.content,
        importance: input.importance ?? 0.5,
        source_metadata: input.source_metadata ?? {},
        kv_triples: input.kv_triples ?? [],
        graph_triples: input.graph_triples ?? [],
      },
    });
    return this.json<Memory>(response);
  }

  async recall(input: {
    q: string;
    session_id?: string;
    limit?: number;
    as_of?: string;
    explain?: boolean;
    token_budget?: number;
  }): Promise<MemorySearchResult> {
    const response = await this.request("GET", "/memories/search", {
      query: {
        q: input.q,
        limit: input.limit ?? 10,
        token_budget: input.token_budget ?? 2048,
        session_id: input.session_id,
        as_of: input.as_of,
        explain: input.explain ? true : undefined,
      },
    });
    return this.json<MemorySearchResult>(response);
  }

  async listMemories(input: {
    session_id?: string;
    memory_type?: string;
    q?: string;
  } = {}): Promise<MemorySearchResult> {
    const response = await this.request("GET", "/memories", {
      query: {
        session_id: input.session_id,
        memory_type: input.memory_type,
        q: input.q,
      },
    });
    return this.json<MemorySearchResult>(response);
  }

  async kvFacts(input: { limit?: number; offset?: number } = {}): Promise<KvFact[]> {
    const response = await this.request("GET", "/kv-facts", {
      query: { limit: input.limit ?? 50, offset: input.offset ?? 0 },
    });
    const body = await this.json<{ facts: KvFact[] }>(response);
    return body.facts ?? [];
  }

  async graphEdges(
    input: { valid_only?: boolean; limit?: number; offset?: number } = {},
  ): Promise<GraphEdge[]> {
    const response = await this.request("GET", "/graph-edges", {
      query: {
        valid_only: input.valid_only ?? true,
        limit: input.limit ?? 50,
        offset: input.offset ?? 0,
      },
    });
    const body = await this.json<{ edges: GraphEdge[] }>(response);
    return body.edges ?? [];
  }

  async update(
    memoryId: string,
    input: { content?: string; importance?: number; memory_type?: string } = {},
  ): Promise<Memory> {
    const body: Record<string, unknown> = {};
    if (input.content !== undefined) body.content = input.content;
    if (input.importance !== undefined) body.importance = input.importance;
    if (input.memory_type !== undefined) body.memory_type = input.memory_type;
    const response = await this.request("PATCH", `/memories/${memoryId}`, { body });
    return this.json<Memory>(response);
  }

  async forget(memoryId: string): Promise<void> {
    const response = await this.request("DELETE", `/memories/${memoryId}`);
    if (!response.ok) {
      await this.parseError(response);
    }
  }

  async emit(input: {
    session_id: string;
    event_type: string;
    payload?: Record<string, unknown>;
  }): Promise<EmitResult> {
    const response = await this.request("POST", "/events", {
      body: {
        session_id: input.session_id,
        event_type: input.event_type,
        payload: input.payload ?? {},
      },
    });
    return this.json<EmitResult>(response);
  }

  async health(): Promise<{ status: string }> {
    const response = await this.request("GET", "/health", { requireKey: false });
    return this.json<{ status: string }>(response);
  }
}
