"""Model protocol — provider-agnostic LLM interface.

Every LLM adapter (Gemini, Anthropic, OpenAI, ...) implements the `Model`
protocol.  The runner talks exclusively through this interface so swapping
providers is a one-line change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Protocol, runtime_checkable


# ------------------------------------------------------------------ #
# Message types                                                       #
# ------------------------------------------------------------------ #


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class ToolCall:
    """A single tool invocation requested by the model."""

    id: str
    name: str
    arguments: dict[str, Any]
    thought_signature: bytes | None = None  # opaque Gemini thought signature


@dataclass
class ToolResult:
    """Result of executing a tool, sent back to the model."""

    call_id: str
    name: str
    content: str
    is_error: bool = False


@dataclass
class Message:
    """A single message in the conversation history."""

    role: Role
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    thought_signature: bytes | None = None  # signature on non-FC text parts


class StopReason(str, Enum):
    END_TURN = "end_turn"
    TOOL_USE = "tool_use"
    MAX_TOKENS = "max_tokens"
    ERROR = "error"


@dataclass
class ModelResponse:
    """Normalised response from any LLM provider."""

    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: StopReason = StopReason.END_TURN
    raw: Any = None  # provider-specific response object
    thinking: str = ""  # concatenated thinking/reasoning parts (if model supports it)
    usage: dict[str, Any] = field(default_factory=dict)  # token usage breakdown
    thought_signature: bytes | None = None  # signature on non-FC text parts


class StreamEventKind(str, Enum):
    """Discriminator for streaming chunks."""

    THINKING_DELTA = "thinking_delta"  # incremental thinking token(s)
    TEXT_DELTA = "text_delta"  # incremental assistant text token(s)
    TOOL_CALL = "tool_call"  # complete tool call (arrives at end of stream)
    FINISH = "finish"  # stream finished — carries final ModelResponse


@dataclass
class ModelStreamEvent:
    """A single chunk emitted during model streaming."""

    kind: StreamEventKind
    delta: str = ""  # text payload for *_delta kinds
    tool_call: ToolCall | None = None  # set when kind == TOOL_CALL
    response: ModelResponse | None = None  # set when kind == FINISH


# ------------------------------------------------------------------ #
# Tool definition (what the model sees)                                #
# ------------------------------------------------------------------ #


@dataclass
class ToolDef:
    """JSON-Schema tool definition sent to the model."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema object


# ------------------------------------------------------------------ #
# Model protocol                                                      #
# ------------------------------------------------------------------ #


@runtime_checkable
class Model(Protocol):
    """Provider-agnostic interface for a chat-completion model."""

    async def generate(
        self,
        messages: list[Message],
        tools: list[ToolDef],
        *,
        system: str = "",
        temperature: float = 0.2,
        max_tokens: int = 8192,
    ) -> ModelResponse:
        """Send messages + tool definitions, return a normalised response."""
        ...

    async def generate_stream(
        self,
        messages: list[Message],
        tools: list[ToolDef],
        *,
        system: str = "",
        temperature: float = 0.2,
        max_tokens: int = 8192,
    ) -> AsyncIterator[ModelStreamEvent]:
        """Stream tokens as ModelStreamEvent chunks.

        The final event always has ``kind == FINISH`` and carries the
        complete ``ModelResponse``.  Providers that don't support native
        streaming may fall back to a single FINISH event.
        """
        ...  # pragma: no cover
        # Need yield for AsyncIterator return type
        yield  # type: ignore[misc]
