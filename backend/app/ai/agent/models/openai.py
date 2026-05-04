"""OpenAI-compatible model adapter for chat completions + tool calling."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, AsyncIterator

from app.ai.agent.model import (
    Message,
    ModelResponse,
    ModelStreamEvent,
    Role,
    StopReason,
    StreamEventKind,
    ToolCall,
    ToolDef,
)

logger = logging.getLogger(__name__)


class OpenAIModel:
    """Model adapter for OpenAI-compatible Chat Completions APIs."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str | None = None,
    ) -> None:
        from openai import AsyncOpenAI

        kwargs: dict[str, Any] = {
            "api_key": api_key or "dummy-key",
        }
        if base_url:
            kwargs["base_url"] = base_url.rstrip("/")
        self._client = AsyncOpenAI(**kwargs)
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
        payload = _build_chat_payload(
            model=self._model,
            messages=messages,
            tools=tools,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        try:
            result = await self._client.chat.completions.create(**payload)
        except Exception as exc:  # noqa: BLE001
            logger.exception("OpenAI generate() failed")
            return ModelResponse(
                content=f"OpenAI request failed: {exc}",
                stop_reason=StopReason.ERROR,
            )
        return _parse_chat_completion(result)

    async def generate_stream(
        self,
        messages: list[Message],
        tools: list[ToolDef],
        *,
        system: str = "",
        temperature: float = 0.2,
        max_tokens: int = 8192,
    ) -> AsyncIterator[ModelStreamEvent]:
        payload = _build_chat_payload(
            model=self._model,
            messages=messages,
            tools=tools,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        payload["stream"] = True

        text_chunks: list[str] = []
        tool_call_buffers: dict[int, dict[str, Any]] = {}
        last_finish_reason: str | None = None
        last_chunk: Any = None

        try:
            stream = await self._client.chat.completions.create(**payload)
            async for chunk in stream:
                last_chunk = chunk
                choice = _first_choice(chunk)
                if choice is None:
                    continue

                delta = _get(choice, "delta")
                if delta is None:
                    continue

                piece = _coerce_delta_content(_get(delta, "content"))
                if piece:
                    text_chunks.append(piece)
                    yield ModelStreamEvent(kind=StreamEventKind.TEXT_DELTA, delta=piece)

                for tc in _iter_tool_call_deltas(delta):
                    index = _get(tc, "index")
                    if index is None:
                        continue
                    buf = tool_call_buffers.setdefault(
                        int(index),
                        {
                            "id": "",
                            "name": "",
                            "args_parts": [],
                        },
                    )
                    tc_id = _get(tc, "id")
                    if tc_id:
                        buf["id"] = tc_id

                    fn = _get(tc, "function")
                    if fn is not None:
                        name = _get(fn, "name")
                        if name:
                            buf["name"] = name
                        args_delta = _get(fn, "arguments")
                        if args_delta:
                            buf["args_parts"].append(args_delta)

                finish_reason = _get(choice, "finish_reason")
                if finish_reason:
                    last_finish_reason = str(finish_reason)

        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "OpenAI generate_stream() failed; trying non-stream fallback"
            )
            fallback = await self.generate(
                messages,
                tools,
                system=system,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if fallback.stop_reason != StopReason.ERROR:
                yield ModelStreamEvent(kind=StreamEventKind.FINISH, response=fallback)
                return
            yield ModelStreamEvent(
                kind=StreamEventKind.FINISH,
                response=ModelResponse(
                    content=f"OpenAI streaming failed: {exc}",
                    stop_reason=StopReason.ERROR,
                ),
            )
            return

        tool_calls = _build_tool_calls_from_buffers(tool_call_buffers)
        for tc in tool_calls:
            yield ModelStreamEvent(kind=StreamEventKind.TOOL_CALL, tool_call=tc)

        stop_reason = _map_finish_reason(
            last_finish_reason, has_tool_calls=bool(tool_calls)
        )
        response = ModelResponse(
            content="".join(text_chunks),
            tool_calls=tool_calls,
            stop_reason=stop_reason,
            raw=last_chunk,
            thinking="",
            usage=_extract_usage(last_chunk),
            thought_signature=None,
        )
        yield ModelStreamEvent(kind=StreamEventKind.FINISH, response=response)


def _build_chat_payload(
    *,
    model: str,
    messages: list[Message],
    tools: list[ToolDef],
    system: str,
    temperature: float,
    max_tokens: int,
) -> dict[str, Any]:
    chat_messages = _messages_to_openai(messages, system=system)
    payload: dict[str, Any] = {
        "model": model,
        "messages": chat_messages,
        "temperature": temperature,
    }
    if max_tokens > 0:
        payload["max_tokens"] = max_tokens
    if tools:
        payload["tools"] = _tool_defs_to_openai(tools)
    return payload


def _messages_to_openai(
    messages: list[Message], *, system: str = ""
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if system:
        out.append({"role": "system", "content": system})

    for msg in messages:
        if msg.role == Role.SYSTEM:
            out.append({"role": "system", "content": msg.content})
            continue

        if msg.role == Role.USER:
            out.append({"role": "user", "content": msg.content})
            continue

        if msg.role == Role.ASSISTANT:
            assistant: dict[str, Any] = {"role": "assistant"}
            if msg.content:
                assistant["content"] = msg.content
            if msg.tool_calls:
                assistant["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                        },
                    }
                    for tc in msg.tool_calls
                ]
            if "content" not in assistant and "tool_calls" in assistant:
                assistant["content"] = ""
            out.append(assistant)
            continue

        if msg.role == Role.TOOL:
            for tr in msg.tool_results:
                out.append(
                    {
                        "role": "tool",
                        "tool_call_id": tr.call_id,
                        "name": tr.name,
                        "content": tr.content,
                    }
                )

    return out


def _tool_defs_to_openai(tool_defs: list[ToolDef]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": td.name,
                "description": td.description,
                "parameters": td.parameters,
            },
        }
        for td in tool_defs
    ]


def _parse_chat_completion(result: Any) -> ModelResponse:
    choice = _first_choice(result)
    if choice is None:
        return ModelResponse(content="", stop_reason=StopReason.ERROR, raw=result)

    message = _get(choice, "message")
    if message is None:
        return ModelResponse(content="", stop_reason=StopReason.ERROR, raw=result)

    content = _coerce_message_content(_get(message, "content"))
    tool_calls = _parse_message_tool_calls(_get(message, "tool_calls"))
    finish_reason = _get(choice, "finish_reason")

    return ModelResponse(
        content=content,
        tool_calls=tool_calls,
        stop_reason=_map_finish_reason(finish_reason, has_tool_calls=bool(tool_calls)),
        raw=result,
        thinking="",
        usage=_extract_usage(result),
        thought_signature=None,
    )


def _parse_message_tool_calls(raw_calls: Any) -> list[ToolCall]:
    calls: list[ToolCall] = []
    for raw in raw_calls or []:
        fn = _get(raw, "function")
        args_obj = _parse_tool_args(_get(fn, "arguments") if fn is not None else None)
        calls.append(
            ToolCall(
                id=str(_get(raw, "id") or uuid.uuid4()),
                name=str(_get(fn, "name") or ""),
                arguments=args_obj,
            )
        )
    return calls


def _build_tool_calls_from_buffers(
    buffers: dict[int, dict[str, Any]],
) -> list[ToolCall]:
    calls: list[ToolCall] = []
    for _, buf in sorted(buffers.items(), key=lambda x: x[0]):
        args_raw = "".join(buf.get("args_parts") or [])
        calls.append(
            ToolCall(
                id=buf.get("id") or str(uuid.uuid4()),
                name=buf.get("name") or "",
                arguments=_parse_tool_args(args_raw),
            )
        )
    return calls


def _parse_tool_args(arguments: Any) -> dict[str, Any]:
    if arguments is None:
        return {}
    if isinstance(arguments, dict):
        return arguments
    if not isinstance(arguments, str):
        return {}
    text = arguments.strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _map_finish_reason(finish_reason: Any, *, has_tool_calls: bool) -> StopReason:
    reason = str(finish_reason or "")
    if reason == "length":
        return StopReason.MAX_TOKENS
    if reason == "tool_calls" or has_tool_calls:
        return StopReason.TOOL_USE
    return StopReason.END_TURN


def _extract_usage(obj: Any) -> dict[str, Any]:
    usage = _get(obj, "usage")
    if usage is None:
        return {}
    return {
        "prompt_tokens": _get(usage, "prompt_tokens"),
        "output_tokens": _get(usage, "completion_tokens"),
        "total_tokens": _get(usage, "total_tokens"),
    }


def _first_choice(obj: Any) -> Any | None:
    choices = _get(obj, "choices") or []
    if not choices:
        return None
    return choices[0]


def _iter_tool_call_deltas(delta: Any) -> list[Any]:
    vals = _get(delta, "tool_calls")
    if vals is None:
        return []
    return list(vals)


def _coerce_message_content(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        text_parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                text_parts.append(item)
                continue
            if isinstance(item, dict):
                if item.get("type") == "text":
                    text_parts.append(str(item.get("text") or ""))
            else:
                if _get(item, "type") == "text":
                    text_parts.append(str(_get(item, "text") or ""))
        return "".join(text_parts)
    return str(value)


def _coerce_delta_content(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        chunks = [str(_get(v, "text") or "") for v in value]
        return "".join(chunks)
    return str(value)


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)
