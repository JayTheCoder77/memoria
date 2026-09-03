const githubFrom =
  "git+https://github.com/JayTheCoder77/memoria.git#subdirectory=apps/mcp-server";

export function mcpConfigSnippet(
  apiUrl = process.env.NEXT_PUBLIC_MEMORY_API_URL ??
    process.env.MEMORY_API_URL ??
    "http://127.0.0.1:8000",
): string {
  return `{
  "mcpServers": {
    "memoria": {
      "command": "uvx",
      "args": [
        "--from",
        "${githubFrom}",
        "memoria-mcp"
      ],
      "env": {
        "MEMORY_API_URL": "${apiUrl}",
        "MEMORY_API_KEY": "mem_...",
        "MEMORY_SESSION_ID": "local"
      }
    }
  }
}`;
}
