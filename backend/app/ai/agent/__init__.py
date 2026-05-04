"""app.ai.agent — Lightweight agent framework.

Public API::

    from app.ai.agent import Agent, Runner, RunContext, tool, Tool
    from app.ai.agent.models import GeminiModel, OpenAIModel
    from app.ai.agent.event_emitter import EventEmitter, JobEventEmitter

Core abstractions:
    - ``Agent``     — declarative config (name, instructions, tools, model)
    - ``Runner``    — execution engine (owns the think→act→observe loop)
    - ``tool``      — decorator that auto-generates JSON Schema from type hints
    - ``RunContext`` — typed dependency injection for tool handlers
    - ``Model``     — provider-agnostic LLM protocol (Gemini/OpenAI adapters included)

Design philosophy: ~600 lines of core, no heavy deps, clean separation.
"""

from app.ai.agent.agent import Agent
from app.ai.agent.context import RunContext
from app.ai.agent.event_emitter import EventEmitter, JobEventEmitter, NullEmitter
from app.ai.agent.model import (
    Message,
    Model,
    ModelResponse,
    Role,
    StopReason,
    ToolCall,
    ToolDef,
    ToolResult,
)
from app.ai.agent.runner import Runner, RunResult
from app.ai.agent.tool import Tool, tool

__all__ = [
    "Agent",
    "EventEmitter",
    "JobEventEmitter",
    "Message",
    "Model",
    "ModelResponse",
    "NullEmitter",
    "Role",
    "RunContext",
    "RunResult",
    "Runner",
    "StopReason",
    "Tool",
    "ToolCall",
    "ToolDef",
    "ToolResult",
    "tool",
]
