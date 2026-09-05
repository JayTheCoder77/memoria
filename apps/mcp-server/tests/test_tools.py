import asyncio

from mcp.server.mcpserver import MCPServer

from mcp_server.server import mcp


def test_mcp_tools_are_registered() -> None:
    assert isinstance(mcp, MCPServer)
    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}
    assert names == {"remember", "recall", "update", "forget", "emit"}
    remember = next(tool for tool in tools if tool.name == "remember")
    required = set(remember.input_schema.get("required", []))
    assert "content" in required
    assert "api_key" not in required
    assert "org_id" not in required


def test_mcp_instructions_tell_agent_to_emit_turns() -> None:
    text = mcp.instructions or ""
    lowered = text.lower()
    assert "emit" in lowered
    assert "session_end" in lowered
    assert "remember" in lowered
    assert "user" in lowered
