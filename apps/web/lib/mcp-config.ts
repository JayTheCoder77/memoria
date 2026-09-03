const githubFrom =
  "git+https://github.com/JayTheCoder77/memoria.git#subdirectory=apps/mcp-server";

export const hostedMemoryApiUrl = "https://memoria-api-jw5g.onrender.com";

export function memoryApiUrl(): string {
  return process.env.NEXT_PUBLIC_MEMORY_API_URL ?? hostedMemoryApiUrl;
}

export function mcpConfigSnippet(apiUrl = memoryApiUrl()): string {
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
        "MEMORY_API_KEY": "mem_..."
      }
    }
  }
}`;
}

export function opencodeConfigSnippet(apiUrl = memoryApiUrl()): string {
  return `{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "memoria": {
      "type": "local",
      "command": [
        "uvx",
        "--from",
        "${githubFrom}",
        "memoria-mcp"
      ],
      "enabled": true,
      "timeout": 60000,
      "environment": {
        "MEMORY_API_URL": "${apiUrl}",
        "MEMORY_API_KEY": "mem_..."
      }
    }
  }
}`;
}
