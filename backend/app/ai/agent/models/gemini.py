"""Gemini model adapter — implements the Model protocol for Google GenAI."""

from __future__ import annotations

import logging
import uuid
from typing import Any, AsyncIterator

from google import genai
from google.genai import types

from app.ai.agent.model import (
    Message,
    ModelResponse,
    ModelStreamEvent,
    Role,
    StopReason,
    StreamEventKind,
    ToolCall,
    ToolDef,
    ToolResult,
)

logger = logging.getLogger(__name__)


class GeminiModel:
    """Model adapter for Google GenAI (``google-genai`` SDK).

    Implements the ``Model`` protocol defined in ``agent.model``.
    """

    def __init__(self, *, api_key: str, model: str = "gemini-2.5-flash-lite") -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model

    async def generate(
        self,
        messages: list[Message],
        tools: list[ToolDef],
        *,
        system: str = "",
        temperature: float = 0.2,
        max_tokens: int = 8192,
    ) -> ModelResponse:
        """Translate our generic types -> Gemini SDK types, call, translate back.

        The google-genai SDK is synchronous, so we offload the blocking call
        to a thread via ``asyncio.to_thread`` to keep the event loop free.
        """
        import asyncio

        contents = _messages_to_contents(messages)
        gemini_tools = _tool_defs_to_gemini(tools) if tools else None

        config = types.GenerateContentConfig(
            system_instruction=system or None,
            tools=gemini_tools,
            temperature=temperature,
            max_output_tokens=max_tokens,
            thinking_config=types.ThinkingConfig(include_thoughts=True),
        )

        # Offload the blocking SDK call to a thread
        result = await asyncio.to_thread(
            self._client.models.generate_content,
            model=self._model,
            contents=contents,
            config=config,
        )

        return _parse_response(result)

    # ------------------------------------------------------------------ #
    # Streaming                                                           #
    # ------------------------------------------------------------------ #

    async def generate_stream(
        self,
        messages: list[Message],
        tools: list[ToolDef],
        *,
        system: str = "",
        temperature: float = 0.2,
        max_tokens: int = 8192,
    ) -> AsyncIterator[ModelStreamEvent]:
        """Stream tokens from Gemini via ``generate_content_stream``.

        Yields ``thinking_delta`` / ``text_delta`` events as chunks arrive,
        then a final ``FINISH`` event carrying the assembled ``ModelResponse``.
        """
        import asyncio

        contents = _messages_to_contents(messages)
        gemini_tools = _tool_defs_to_gemini(tools) if tools else None

        config = types.GenerateContentConfig(
            system_instruction=system or None,
            tools=gemini_tools,
            temperature=temperature,
            max_output_tokens=max_tokens,
            thinking_config=types.ThinkingConfig(include_thoughts=True),
        )

        # The SDK's generate_content_stream is synchronous (returns Iterator).
        # Run in a thread so we don't block the event loop, and feed chunks
        # back via an asyncio.Queue.
        chunk_queue: asyncio.Queue[Any] = asyncio.Queue()
        _SENTINEL = object()

        def _run_stream() -> None:
            try:
                for chunk in self._client.models.generate_content_stream(
                    model=self._model,
                    contents=contents,
                    config=config,
                ):
                    chunk_queue.put_nowait(chunk)
            except Exception as exc:
                chunk_queue.put_nowait(exc)
            finally:
                chunk_queue.put_nowait(_SENTINEL)

        loop = asyncio.get_running_loop()
        loop.run_in_executor(None, _run_stream)

        # Accumulate full response while yielding deltas
        text_chunks: list[str] = []
        thinking_chunks: list[str] = []
        tool_calls: list[ToolCall] = []
        last_chunk: Any = None
        # Track the latest thought_signature seen on non-FC parts (text/thought)
        last_text_thought_signature: bytes | None = None

        while True:
            item = await chunk_queue.get()

            if item is _SENTINEL:
                break

            if isinstance(item, Exception):
                # Surface as an error ModelResponse
                yield ModelStreamEvent(
                    kind=StreamEventKind.FINISH,
                    response=ModelResponse(
                        content="",
                        stop_reason=StopReason.ERROR,
                    ),
                )
                return

            last_chunk = item

            # Each chunk is a GenerateContentResponse with partial parts
            cand = item.candidates[0] if item.candidates else None
            if cand is None or cand.content is None:
                continue

            for part in cand.content.parts or []:
                sig = getattr(part, "thought_signature", None)
                if getattr(part, "thought", False) and part.text:
                    thinking_chunks.append(part.text)
                    if sig is not None:
                        last_text_thought_signature = sig
                    yield ModelStreamEvent(
                        kind=StreamEventKind.THINKING_DELTA,
                        delta=part.text,
                    )
                elif part.function_call:
                    fc = part.function_call
                    tc = ToolCall(
                        id=fc.id or str(uuid.uuid4()),
                        name=fc.name or "",
                        arguments=dict(fc.args or {}),
                        thought_signature=sig,
                    )
                    tool_calls.append(tc)
                    yield ModelStreamEvent(
                        kind=StreamEventKind.TOOL_CALL,
                        tool_call=tc,
                    )
                elif part.text:
                    text_chunks.append(part.text)
                    if sig is not None:
                        last_text_thought_signature = sig
                    yield ModelStreamEvent(
                        kind=StreamEventKind.TEXT_DELTA,
                        delta=part.text,
                    )

        # Build final assembled ModelResponse
        stop_reason = StopReason.TOOL_USE if tool_calls else StopReason.END_TURN

        usage: dict[str, Any] = {}
        if last_chunk is not None:
            um = getattr(last_chunk, "usage_metadata", None)
            if um is not None:
                usage = {
                    "prompt_tokens": getattr(um, "prompt_token_count", None),
                    "output_tokens": getattr(um, "candidates_token_count", None),
                    "thinking_tokens": getattr(um, "thoughts_token_count", None),
                }

        response = ModelResponse(
            content="\n".join(text_chunks),
            tool_calls=tool_calls,
            stop_reason=stop_reason,
            raw=last_chunk,
            thinking="\n".join(thinking_chunks),
            usage=usage,
            thought_signature=last_text_thought_signature,
        )

        yield ModelStreamEvent(
            kind=StreamEventKind.FINISH,
            response=response,
        )


# ------------------------------------------------------------------ #
# Internal: message conversion                                        #
# ------------------------------------------------------------------ #


def _messages_to_contents(messages: list[Message]) -> list[types.Content]:
    """Convert our generic Message list to Gemini Content list."""
    contents: list[types.Content] = []

    for msg in messages:
        if msg.role == Role.USER:
            contents.append(
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=msg.content)],
                )
            )

        elif msg.role == Role.ASSISTANT:
            parts: list[types.Part] = []
            if msg.content:
                # Attach thought_signature to the text part if present
                # (Gemini 3: signature on last text part when no FCs)
                text_part = types.Part.from_text(text=msg.content)
                if msg.thought_signature is not None and not msg.tool_calls:
                    text_part.thought_signature = msg.thought_signature
                parts.append(text_part)
            for tc in msg.tool_calls:
                fc_part = types.Part(
                    function_call=types.FunctionCall(
                        id=tc.id,
                        name=tc.name,
                        args=tc.arguments,
                    )
                )
                # Preserve thought_signature on the function_call Part
                if tc.thought_signature is not None:
                    fc_part.thought_signature = tc.thought_signature
                parts.append(fc_part)
            if parts:
                contents.append(types.Content(role="model", parts=parts))

        elif msg.role == Role.TOOL:
            parts_list: list[types.Part] = []
            for tr in msg.tool_results:
                fr = types.FunctionResponse(
                    name=tr.name,
                    response={"result": tr.content},
                )
                if tr.call_id:
                    fr.id = tr.call_id
                parts_list.append(types.Part(function_response=fr))
            if parts_list:
                contents.append(types.Content(role="function", parts=parts_list))

    return contents


def _tool_defs_to_gemini(tool_defs: list[ToolDef]) -> list[types.Tool]:
    """Convert our ToolDef list to Gemini function declarations."""
    decls = [
        types.FunctionDeclaration(
            name=td.name,
            description=td.description,
            parameters_json_schema=td.parameters,
        )
        for td in tool_defs
    ]
    return [types.Tool(function_declarations=decls)]


# ------------------------------------------------------------------ #
# Internal: response parsing                                          #
# ------------------------------------------------------------------ #


def _parse_response(result: Any) -> ModelResponse:
    """Parse a Gemini GenerateContentResponse into our ModelResponse."""
    cand = result.candidates[0] if result.candidates else None
    if cand is None or cand.content is None:
        return ModelResponse(
            content="",
            stop_reason=StopReason.ERROR,
            raw=result,
        )

    parts = list(cand.content.parts or [])

    # Collect text, thinking, and tool calls
    text_chunks: list[str] = []
    thinking_chunks: list[str] = []
    tool_calls: list[ToolCall] = []
    last_text_thought_signature: bytes | None = None

    for part in parts:
        sig = getattr(part, "thought_signature", None)
        if getattr(part, "thought", False) and part.text:
            thinking_chunks.append(part.text)
            if sig is not None:
                last_text_thought_signature = sig
        elif part.function_call:
            fc = part.function_call
            tool_calls.append(
                ToolCall(
                    id=fc.id or str(uuid.uuid4()),
                    name=fc.name or "",
                    arguments=dict(fc.args or {}),
                    thought_signature=sig,
                )
            )
        elif part.text:
            text_chunks.append(part.text)
            if sig is not None:
                last_text_thought_signature = sig

    stop_reason = StopReason.TOOL_USE if tool_calls else StopReason.END_TURN

    # Extract usage metadata
    usage: dict[str, Any] = {}
    um = getattr(result, "usage_metadata", None)
    if um is not None:
        usage = {
            "prompt_tokens": getattr(um, "prompt_token_count", None),
            "output_tokens": getattr(um, "candidates_token_count", None),
            "thinking_tokens": getattr(um, "thoughts_token_count", None),
        }

    return ModelResponse(
        content="\n".join(text_chunks),
        tool_calls=tool_calls,
        stop_reason=stop_reason,
        raw=result,
        thinking="\n".join(thinking_chunks),
        usage=usage,
        thought_signature=last_text_thought_signature,
    )
