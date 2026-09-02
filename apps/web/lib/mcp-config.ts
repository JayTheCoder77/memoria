export const mcpConfigSnippet = `{
  "mcpServers": {
    "memoria": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/memoria/apps/mcp-server", "python", "-m", "mcp_server"],
      "env": {
        "MEMORY_API_URL": "http://127.0.0.1:8000"
      }
    }
  }
}`;
