"""MCP client — connects to MCP servers via stdio or Streamable HTTP.

Provides a uniform interface for discovering and calling tools from
external MCP servers.  Designed so the Runner treats MCP tools identically
to local ``@tool``-decorated functions.

Requires the ``mcp`` package (optional dependency)::

    pip install mcp

Usage::

    from app.ai.agent.mcp import MCPServer

    # Local stdio server
    server = MCPServer.stdio("npx", args=["-y", "@modelcontextprotocol/server-filesystem", "/data"])

    # Remote HTTP server
    server = MCPServer.http("https://mcp.example.com/mcp")

    # Use in an agent
    agent = Agent(
        name="file_agent",
        mcp_servers=[server],
    )
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from app.ai.agent.context import RunContext
from app.ai.agent.model import ToolDef
from app.ai.agent.tool import Tool

logger = logging.getLogger(__name__)


@dataclass
class MCPServer:
    """Connects to a single MCP server and exposes its tools.

    This is a lightweight wrapper that lazily connects to the server on
    first ``list_tools()`` call.
    """

    transport: str  # "stdio" or "http"
    command: str | None = None
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    url: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    cache_tools: bool = True
    _cached_tools: list[Tool] | None = field(default=None, init=False, repr=False)
    _session: Any = field(default=None, init=False, repr=False)

    @classmethod
    def stdio(
        cls,
        command: str,
        *,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        cache_tools: bool = True,
    ) -> MCPServer:
        """Create an MCP server with stdio transport (local process)."""
        return cls(
            transport="stdio",
            command=command,
            args=args or [],
            env=env or {},
            cache_tools=cache_tools,
        )

    @classmethod
    def http(
        cls,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        cache_tools: bool = True,
    ) -> MCPServer:
        """Create an MCP server with Streamable HTTP transport (remote)."""
        return cls(
            transport="http",
            url=url,
            headers=headers or {},
            cache_tools=cache_tools,
        )

    async def list_tools(self) -> list[Tool]:
        """Discover available tools from the MCP server.

        Returns Tool instances that can be registered with an Agent.
        The tools call back to this server when executed.
        """
        if self.cache_tools and self._cached_tools is not None:
            return self._cached_tools

        try:
            raw_tools = await self._discover_tools()
        except ImportError:
            logger.error("MCP package not installed. Install with: pip install mcp")
            return []
        except Exception as exc:
            logger.error("Failed to discover MCP tools: %s", exc)
            return []

        tools: list[Tool] = []
        for rt in raw_tools:
            tool = self._wrap_mcp_tool(rt)
            tools.append(tool)

        if self.cache_tools:
            self._cached_tools = tools

        return tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Call a tool on the MCP server and return the result as a string."""
        try:
            from mcp import ClientSession
            from mcp.client.stdio import stdio_client, StdioServerParameters
            from mcp.client.streamable_http import streamablehttp_client

            if self.transport == "stdio":
                params = StdioServerParameters(
                    command=self.command or "",
                    args=self.args,
                    env=self.env or None,
                )
                async with stdio_client(params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        result = await session.call_tool(name, arguments)
                        return _serialize_mcp_result(result)

            elif self.transport == "http":
                async with streamablehttp_client(
                    self.url or "", headers=self.headers
                ) as (read, write, _):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        result = await session.call_tool(name, arguments)
                        return _serialize_mcp_result(result)

            else:
                return json.dumps({"error": f"Unknown transport: {self.transport}"})

        except ImportError:
            return json.dumps({"error": "MCP package not installed"})
        except Exception as exc:
            logger.exception("MCP tool call failed: %s(%s)", name, arguments)
            return json.dumps({"error": str(exc)})

    async def _discover_tools(self) -> list[dict[str, Any]]:
        """Connect to the MCP server and list tools."""
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client, StdioServerParameters
        from mcp.client.streamable_http import streamablehttp_client

        if self.transport == "stdio":
            params = StdioServerParameters(
                command=self.command or "",
                args=self.args,
                env=self.env or None,
            )
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.list_tools()
                    return [
                        {
                            "name": t.name,
                            "description": t.description or "",
                            "input_schema": t.inputSchema
                            or {"type": "object", "properties": {}},
                        }
                        for t in result.tools
                    ]

        elif self.transport == "http":
            async with streamablehttp_client(self.url or "", headers=self.headers) as (
                read,
                write,
                _,
            ):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.list_tools()
                    return [
                        {
                            "name": t.name,
                            "description": t.description or "",
                            "input_schema": t.inputSchema
                            or {"type": "object", "properties": {}},
                        }
                        for t in result.tools
                    ]

        return []

    def _wrap_mcp_tool(self, raw: dict[str, Any]) -> Tool:
        """Wrap an MCP tool definition as a local Tool that delegates to call_tool."""
        name = raw["name"]
        description = raw.get("description", "")
        input_schema = raw.get("input_schema", {"type": "object", "properties": {}})
        server = self  # capture reference

        async def _mcp_executor(ctx: RunContext[Any], **kwargs: Any) -> str:
            return await server.call_tool(name, kwargs)

        td = ToolDef(
            name=name,
            description=description,
            parameters=input_schema,
        )

        return Tool(
            name=name,
            description=description,
            func=_mcp_executor,
            takes_ctx=True,
            tool_def=td,
            is_async=True,
        )


def _serialize_mcp_result(result: Any) -> str:
    """Serialize an MCP CallToolResult to a JSON string."""
    if hasattr(result, "content"):
        parts = []
        for item in result.content:
            if hasattr(item, "text"):
                parts.append(item.text)
            else:
                parts.append(str(item))
        return "\n".join(parts) if parts else "{}"
    return json.dumps({"result": str(result)})
