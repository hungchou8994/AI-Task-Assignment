"""MCP types — tool/resource definitions for Model Context Protocol servers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.ai.agent.model import ToolDef
from app.ai.agent.tool import Tool


@dataclass
class MCPToolDef:
    """An MCP tool discovered at runtime, wrapped as a local Tool."""

    name: str
    description: str
    input_schema: dict[str, Any]
    server: Any = None  # reference to the parent MCPServer

    @property
    def tool_def(self) -> ToolDef:
        return ToolDef(
            name=self.name,
            description=self.description,
            parameters=self.input_schema,
        )


@dataclass
class MCPResource:
    """A resource exposed by an MCP server."""

    uri: str
    name: str
    description: str = ""
    mime_type: str = "text/plain"


@dataclass
class MCPServerConfig:
    """Configuration for connecting to an MCP server."""

    transport: str  # "stdio" or "http"
    command: str | None = None  # for stdio
    args: list[str] = field(default_factory=list)  # for stdio
    env: dict[str, str] = field(default_factory=dict)  # for stdio
    url: str | None = None  # for http
    headers: dict[str, str] = field(default_factory=dict)  # for http
    cache_tools: bool = True
