import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

from app.ai.agent.model import Message, Role, StopReason, ToolCall, ToolDef, ToolResult
from app.ai.agent.models.openai import (
    _build_tool_calls_from_buffers,
    _map_finish_reason,
    _messages_to_openai,
    _parse_chat_completion,
    _tool_defs_to_openai,
)


class _Obj:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def test_messages_to_openai_maps_tool_history():
    messages = [
        Message(role=Role.USER, content="hello"),
        Message(
            role=Role.ASSISTANT,
            content="calling tool",
            tool_calls=[
                ToolCall(id="call_1", name="lookup", arguments={"query": "abc"})
            ],
        ),
        Message(
            role=Role.TOOL,
            tool_results=[
                ToolResult(call_id="call_1", name="lookup", content='{"ok":true}')
            ],
        ),
    ]

    out = _messages_to_openai(messages, system="sys")
    assert out[0] == {"role": "system", "content": "sys"}
    assert out[1] == {"role": "user", "content": "hello"}
    assert out[2]["role"] == "assistant"
    assert out[2]["tool_calls"][0]["id"] == "call_1"
    assert out[3]["role"] == "tool"
    assert out[3]["tool_call_id"] == "call_1"


def test_tool_defs_to_openai_maps_schema():
    defs = [
        ToolDef(
            name="search",
            description="search items",
            parameters={"type": "object", "properties": {"q": {"type": "string"}}},
        )
    ]
    out = _tool_defs_to_openai(defs)
    assert out[0]["type"] == "function"
    assert out[0]["function"]["name"] == "search"
    assert out[0]["function"]["parameters"]["properties"]["q"]["type"] == "string"


def test_parse_chat_completion_with_tool_calls():
    result = _Obj(
        choices=[
            _Obj(
                finish_reason="tool_calls",
                message=_Obj(
                    content="",
                    tool_calls=[
                        _Obj(
                            id="call_x",
                            function=_Obj(name="do_thing", arguments='{"x":1}'),
                        )
                    ],
                ),
            )
        ],
        usage=_Obj(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )

    parsed = _parse_chat_completion(result)
    assert parsed.stop_reason == StopReason.TOOL_USE
    assert len(parsed.tool_calls) == 1
    assert parsed.tool_calls[0].name == "do_thing"
    assert parsed.tool_calls[0].arguments == {"x": 1}
    assert parsed.usage["total_tokens"] == 15


def test_build_tool_calls_from_stream_buffers():
    buffers = {
        0: {"id": "call_1", "name": "lookup", "args_parts": ['{"a"', ":1}"]},
        1: {"id": "", "name": "noop", "args_parts": [""]},
    }
    calls = _build_tool_calls_from_buffers(buffers)
    assert calls[0].id == "call_1"
    assert calls[0].arguments == {"a": 1}
    assert calls[1].name == "noop"
    assert calls[1].arguments == {}


def test_map_finish_reason_variants():
    assert _map_finish_reason("tool_calls", has_tool_calls=False) == StopReason.TOOL_USE
    assert _map_finish_reason("length", has_tool_calls=False) == StopReason.MAX_TOKENS
    assert _map_finish_reason("stop", has_tool_calls=False) == StopReason.END_TURN
    assert _map_finish_reason(None, has_tool_calls=True) == StopReason.TOOL_USE
