"""Unit tests for the agent framework (app/ai/agent/).

Covers: @tool decorator, skill loader, loop detector, runner, context, emitter.
Run: docker compose exec api python -m pytest tests/test_agent_framework.py -x -q
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")

import asyncio
import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator

import pytest

from app.ai.agent import (
    Agent,
    EventEmitter,
    Message,
    Model,
    ModelResponse,
    NullEmitter,
    Role,
    RunContext,
    RunResult,
    Runner,
    StopReason,
    Tool,
    ToolCall,
    ToolDef,
    ToolResult,
    tool,
)
from app.ai.agent.model import ModelStreamEvent, StreamEventKind
from app.ai.agent.loop_detector import LoopAction, ToolLoopDetector
from app.ai.agent.skills import (
    _parse_frontmatter,
    _strip_frontmatter,
    load_skill_file,
    load_skills,
    resolve_skill_sources,
)
from app.ai.agent.tool import (
    _json_schema_type,
    _parse_docstring_args,
    scrub_tool_output,
)


# ================================================================== #
# Fixtures / helpers                                                   #
# ================================================================== #


@dataclass
class FakeDeps:
    """Minimal deps for testing."""

    items: list[str] = field(default_factory=list)
    finalized: Any = None


class MockModel:
    """A mock model that returns scripted responses.

    Pass a list of ModelResponse objects; each call to generate() pops
    the next one.  After the script is exhausted, returns end_turn.
    """

    def __init__(self, responses: list[ModelResponse]) -> None:
        self._responses = list(responses)
        self.call_count = 0
        self.last_messages: list[Message] = []
        self.last_tools: list[ToolDef] = []
        self.last_system: str = ""

    async def generate(
        self,
        messages: list[Message],
        tools: list[ToolDef],
        *,
        system: str = "",
        temperature: float = 0.2,
        max_tokens: int = 8192,
    ) -> ModelResponse:
        self.call_count += 1
        self.last_messages = messages
        self.last_tools = tools
        self.last_system = system
        if self._responses:
            return self._responses.pop(0)
        return ModelResponse(content="done", stop_reason=StopReason.END_TURN)

    async def generate_stream(
        self,
        messages: list[Message],
        tools: list[ToolDef],
        *,
        system: str = "",
        temperature: float = 0.2,
        max_tokens: int = 8192,
    ) -> AsyncIterator[ModelStreamEvent]:
        """Streaming mock — delegates to generate() and yields a single FINISH event."""
        response = await self.generate(
            messages,
            tools,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        yield ModelStreamEvent(kind=StreamEventKind.FINISH, response=response)


# ================================================================== #
# @tool decorator tests                                               #
# ================================================================== #


class TestToolDecorator:
    def test_bare_decorator(self):
        """@tool with no parentheses creates a Tool with correct name."""

        @tool
        def greet(name: str) -> str:
            """Say hello."""
            return f"Hello, {name}"

        assert isinstance(greet, Tool)
        assert greet.name == "greet"
        assert greet.description == "Say hello."
        assert greet.takes_ctx is False

    def test_decorator_with_arguments(self):
        """@tool(name=..., description=...) overrides defaults."""

        @tool(name="custom_greet", description="A custom greeting tool")
        def greet(name: str) -> str:
            """Original docstring."""
            return f"Hello, {name}"

        assert greet.name == "custom_greet"
        assert greet.description == "A custom greeting tool"

    def test_context_injection(self):
        """First RunContext param is hidden from schema and injected at call time."""

        @tool
        def get_items(ctx: RunContext[FakeDeps], limit: int = 10) -> str:
            """List items.

            Args:
                limit: Max items to return.
            """
            return json.dumps(ctx.deps.items[:limit])

        assert get_items.takes_ctx is True
        schema = get_items.tool_def.parameters
        # RunContext should NOT appear in the schema
        assert "ctx" not in schema["properties"]
        assert "limit" in schema["properties"]
        assert schema["properties"]["limit"]["type"] == "integer"
        assert schema["properties"]["limit"]["description"] == "Max items to return."

    def test_required_params(self):
        """Parameters without defaults are required in schema."""

        @tool
        def search(query: str, limit: int = 5) -> str:
            """Search things.

            Args:
                query: The search query.
                limit: Max results.
            """
            return query

        schema = search.tool_def.parameters
        assert "required" in schema
        assert "query" in schema["required"]
        assert "limit" not in schema["required"]

    def test_list_param_type(self):
        """list[str] becomes {type: array, items: {type: string}}."""

        @tool
        def tag(ctx: RunContext[FakeDeps], tags: list[str]) -> str:
            """Tag items.

            Args:
                tags: Tags to apply.
            """
            return str(tags)

        schema = tag.tool_def.parameters
        assert schema["properties"]["tags"]["type"] == "array"
        assert schema["properties"]["tags"]["items"]["type"] == "string"

    def test_dict_param_type(self):
        """dict[str, int] becomes {type: object, additionalProperties: {type: integer}}."""

        @tool
        def counts(data: dict[str, int]) -> str:
            """Count things."""
            return str(data)

        schema = counts.tool_def.parameters
        assert schema["properties"]["data"]["type"] == "object"
        assert schema["properties"]["data"]["additionalProperties"]["type"] == "integer"

    def test_execute_without_context(self):
        """Tool.execute works for context-free tools."""

        @tool
        def add(a: int, b: int) -> str:
            """Add two numbers."""
            return json.dumps({"sum": a + b})

        result = asyncio.run(add.execute(None, {"a": 3, "b": 4}))
        assert json.loads(result) == {"sum": 7}

    def test_execute_with_context(self):
        """Tool.execute injects RunContext when tool expects it."""

        @tool
        def count(ctx: RunContext[FakeDeps]) -> str:
            """Count items."""
            return json.dumps({"count": len(ctx.deps.items)})

        deps = FakeDeps(items=["a", "b", "c"])
        ctx = RunContext(deps=deps, agent_name="test")
        result = asyncio.run(count.execute(ctx, {}))
        assert json.loads(result) == {"count": 3}


# ================================================================== #
# Docstring parsing tests                                             #
# ================================================================== #


class TestDocstringParsing:
    def test_google_style_args(self):
        """Parses standard Google-style Args section."""
        doc = """Do something important.

        Args:
            name: The person's name.
            age: How old they are.

        Returns:
            A greeting string.
        """
        result = _parse_docstring_args(doc)
        assert result["name"] == "The person's name."
        assert result["age"] == "How old they are."
        assert "Returns" not in result

    def test_multiline_description(self):
        """Continuation lines are joined into the description."""
        doc = """Tool.

        Args:
            query: The search query that will be
                used across multiple indices.
            limit: Max results.
        """
        result = _parse_docstring_args(doc)
        assert "multiple indices" in result["query"]
        assert result["limit"] == "Max results."

    def test_empty_docstring(self):
        result = _parse_docstring_args(None)
        assert result == {}

    def test_no_args_section(self):
        result = _parse_docstring_args("Just a simple function.")
        assert result == {}


# ================================================================== #
# JSON Schema type mapping                                            #
# ================================================================== #


class TestJsonSchemaType:
    def test_str(self):
        assert _json_schema_type(str) == {"type": "string"}

    def test_int(self):
        assert _json_schema_type(int) == {"type": "integer"}

    def test_float(self):
        assert _json_schema_type(float) == {"type": "number"}

    def test_bool(self):
        assert _json_schema_type(bool) == {"type": "boolean"}

    def test_list_of_str(self):
        schema = _json_schema_type(list[str])
        assert schema == {"type": "array", "items": {"type": "string"}}

    def test_dict_str_int(self):
        schema = _json_schema_type(dict[str, int])
        assert schema == {"type": "object", "additionalProperties": {"type": "integer"}}


# ================================================================== #
# scrub_tool_output tests                                             #
# ================================================================== #


class TestScrubToolOutput:
    def test_short_output_unchanged(self):
        assert scrub_tool_output("hello") == "hello"

    def test_long_output_truncated(self):
        text = "x" * 20_000
        result = scrub_tool_output(text, max_chars=100)
        assert len(result) < len(text)
        assert "[truncated]" in result


# ================================================================== #
# Skills loader tests                                                 #
# ================================================================== #


class TestSkillsLoader:
    def test_strip_frontmatter(self):
        text = "---\nname: test\n---\n\n# Body\nContent here."
        body = _strip_frontmatter(text)
        assert body.startswith("# Body")
        assert "name: test" not in body

    def test_parse_frontmatter(self):
        text = "---\nname: my_skill\ndescription: A test skill\n---\n\nBody"
        meta = _parse_frontmatter(text)
        assert meta["name"] == "my_skill"
        assert meta["description"] == "A test skill"

    def test_no_frontmatter(self):
        text = "# Just a heading\nSome content."
        body = _strip_frontmatter(text)
        assert body == text
        meta = _parse_frontmatter(text)
        assert meta == {}

    def test_load_skill_file(self, tmp_path: Path):
        skill_file = tmp_path / "test_skill.md"
        skill_file.write_text(
            "---\nname: test\n---\n\n# Test Skill\n\nHello, world!",
            encoding="utf-8",
        )
        body = load_skill_file(skill_file)
        assert body == "# Test Skill\n\nHello, world!"

    def test_load_skills_by_name(self, tmp_path: Path):
        """Skills resolved by name from skills_dir."""
        skill_file = tmp_path / "alpha.md"
        skill_file.write_text(
            "---\nname: alpha\n---\n\nAlpha content.", encoding="utf-8"
        )
        result = load_skills(["alpha"], skills_dir=tmp_path)
        assert "Alpha content." in result

    def test_load_skills_nested_directory(self, tmp_path: Path):
        """Skills resolved from nested dir/SKILL.md convention."""
        skill_dir = tmp_path / "beta"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: beta\n---\n\nBeta content.", encoding="utf-8"
        )
        result = load_skills(["beta"], skills_dir=tmp_path)
        assert "Beta content." in result

    def test_load_skills_missing_skill(self, tmp_path: Path):
        """Missing skill is skipped with a warning, not an error."""
        result = load_skills(["nonexistent"], skills_dir=tmp_path)
        assert result == ""

    def test_resolve_skill_sources_callable(self):
        """Callable skill sources are invoked."""
        result = resolve_skill_sources([lambda: "Dynamic skill content"])
        assert result == "Dynamic skill content"

    def test_resolve_skill_sources_path(self, tmp_path: Path):
        """Path skill sources are loaded as files."""
        skill_file = tmp_path / "path_skill.md"
        skill_file.write_text("---\nname: path\n---\n\nPath content.", encoding="utf-8")
        result = resolve_skill_sources([skill_file])
        assert "Path content." in result

    def test_resolve_skill_sources_mixed(self, tmp_path: Path):
        """Mix of str, Path, and callable sources."""
        skill_file = tmp_path / "mixed.md"
        skill_file.write_text("---\nname: mixed\n---\n\nFile skill.", encoding="utf-8")

        result = resolve_skill_sources(
            [
                "mixed",
                lambda: "Lambda skill",
            ],
            skills_dir=tmp_path,
        )
        assert "File skill." in result
        assert "Lambda skill" in result

    def test_multiple_skills_joined(self, tmp_path: Path):
        """Multiple skills are joined with separator."""
        (tmp_path / "a.md").write_text("---\nname: a\n---\n\nSkill A", encoding="utf-8")
        (tmp_path / "b.md").write_text("---\nname: b\n---\n\nSkill B", encoding="utf-8")
        result = load_skills(["a", "b"], skills_dir=tmp_path)
        assert "Skill A" in result
        assert "Skill B" in result
        assert "---" in result  # separator


# ================================================================== #
# LoopDetector tests                                                  #
# ================================================================== #


class TestLoopDetector:
    def test_no_loop_initially(self):
        det = ToolLoopDetector()
        action = det.record_tool_call("analyze", '{"x":1}', '{"result":"ok"}')
        assert action == LoopAction.NONE

    def test_exact_call_warns(self):
        det = ToolLoopDetector(exact_warn=2, exact_stop=4)
        det.record_tool_call("analyze", '{"x":1}', "r1")
        action = det.record_tool_call("analyze", '{"x":1}', "r2")
        assert action == LoopAction.WARN

    def test_exact_call_stops(self):
        det = ToolLoopDetector(exact_warn=2, exact_stop=3)
        det.record_tool_call("analyze", '{"x":1}', "r1")
        det.record_tool_call("analyze", '{"x":1}', "r2")
        action = det.record_tool_call("analyze", '{"x":1}', "r3")
        assert action == LoopAction.STOP

    def test_different_args_no_loop(self):
        det = ToolLoopDetector(exact_warn=2, exact_stop=3)
        a1 = det.record_tool_call("analyze", '{"x":1}', "r1")
        a2 = det.record_tool_call("analyze", '{"x":2}', "r2")
        a3 = det.record_tool_call("analyze", '{"x":3}', "r3")
        assert a1 == LoopAction.NONE
        assert a2 == LoopAction.NONE
        assert a3 == LoopAction.NONE

    def test_read_only_streak_warns(self):
        det = ToolLoopDetector(
            read_only_warn=3,
            read_only_stop=5,
            mutating_tools={"finalize"},
        )
        det.record_tool_call("read_a", "{}", "r1")
        det.record_tool_call("read_b", "{}", "r2")
        action = det.record_tool_call("read_c", "{}", "r3")
        assert action >= LoopAction.WARN

    def test_mutating_tool_resets_streak(self):
        det = ToolLoopDetector(
            read_only_warn=3,
            read_only_stop=5,
            mutating_tools={"finalize"},
        )
        det.record_tool_call("read_a", "{}", "r1")
        det.record_tool_call("read_b", "{}", "r2")
        # Mutating tool resets the read-only streak
        det.record_tool_call("finalize", "{}", "r3")
        action = det.record_tool_call("read_d", "{}", "r4")
        # Streak is only 1 now, should be NONE
        assert action == LoopAction.NONE

    def test_same_result_warns(self):
        det = ToolLoopDetector(same_result_warn=2, same_result_stop=4)
        det.record_tool_call("analyze", '{"a":1}', "same_output")
        action = det.record_tool_call("analyze", '{"a":2}', "same_output")
        assert action >= LoopAction.WARN

    def test_warn_message(self):
        msg = ToolLoopDetector.warn_message()
        assert "loop" in msg.lower()

    def test_stop_message(self):
        msg = ToolLoopDetector.stop_message()
        assert "finalize" in msg.lower()


# ================================================================== #
# RunContext tests                                                     #
# ================================================================== #


class TestRunContext:
    def test_basic_context(self):
        deps = FakeDeps(items=["a", "b"])
        ctx = RunContext(deps=deps, agent_name="test")
        assert ctx.deps.items == ["a", "b"]
        assert ctx.agent_name == "test"
        assert ctx.iteration == 0
        assert ctx.usage == {}

    def test_deps_generic_typing(self):
        """RunContext preserves the deps type at runtime."""
        deps = FakeDeps()
        ctx: RunContext[FakeDeps] = RunContext(deps=deps)
        ctx.deps.items.append("x")
        assert ctx.deps.items == ["x"]


# ================================================================== #
# EventEmitter tests                                                  #
# ================================================================== #


class TestEventEmitter:
    def test_null_emitter_no_crash(self):
        """NullEmitter silently discards events."""
        emitter = NullEmitter()
        emitter.emit("test_event", iteration=1, message="hello")
        # Should not raise

    def test_null_emitter_implements_protocol(self):
        """NullEmitter satisfies EventEmitter protocol."""
        emitter = NullEmitter()
        assert isinstance(emitter, EventEmitter)


# ================================================================== #
# Agent config tests                                                  #
# ================================================================== #


class TestAgentConfig:
    def test_default_agent(self):
        agent = Agent()
        assert agent.name == "agent"
        assert agent.max_iterations == 20

    def test_get_model_from_instance(self):
        model = MockModel([])
        agent = Agent(model=model)
        assert agent.get_model() is model

    def test_get_model_from_factory(self):
        model = MockModel([])
        agent = Agent(model=lambda: model)
        resolved = agent.get_model()
        assert resolved is model

    def test_get_model_raises_when_none(self):
        agent = Agent()
        with pytest.raises(ValueError, match="no model configured"):
            agent.get_model()


# ================================================================== #
# Runner integration tests (with MockModel)                           #
# ================================================================== #


class TestRunner:
    # Requirement mapping:
    # - ASYNC-03: Runner.run_sync remains available for sync callers
    # - TEST-02: explicit regression coverage for direct Runner.run_sync usage

    def test_simple_end_turn(self):
        """Model returns immediately with no tool calls — single iteration."""
        model = MockModel(
            [ModelResponse(content="All done.", stop_reason=StopReason.END_TURN)]
        )
        agent = Agent(name="test", model=model, max_iterations=5, empty_rounds_cap=1)

        result = Runner.run_sync(agent, "Hello")

        assert isinstance(result, RunResult)
        assert result.iterations >= 1
        assert model.call_count >= 1

    def test_tool_call_then_end(self):
        """Model calls a tool, gets result, then ends."""

        @tool
        def greet(name: str) -> str:
            """Say hello."""
            return json.dumps({"greeting": f"Hello, {name}!"})

        model = MockModel(
            [
                # First: call the greet tool
                ModelResponse(
                    content="Let me greet you.",
                    tool_calls=[
                        ToolCall(id="tc1", name="greet", arguments={"name": "World"})
                    ],
                    stop_reason=StopReason.TOOL_USE,
                ),
                # Second: done
                ModelResponse(
                    content="Greeting complete.",
                    stop_reason=StopReason.END_TURN,
                ),
            ]
        )

        agent = Agent(
            name="greeter",
            model=model,
            tools=[greet],
            max_iterations=5,
            empty_rounds_cap=3,
        )

        result = Runner.run_sync(agent, "Please greet the world")

        assert result.iterations >= 2
        # Model called at least twice: once for tool call, once for end_turn
        assert model.call_count >= 2

    def test_tool_with_deps(self):
        """Tool receives RunContext with deps correctly."""

        @tool
        def add_item(ctx: RunContext[FakeDeps], item: str) -> str:
            """Add an item.

            Args:
                item: Item to add.
            """
            ctx.deps.items.append(item)
            return json.dumps({"added": item, "count": len(ctx.deps.items)})

        model = MockModel(
            [
                ModelResponse(
                    content="Adding item.",
                    tool_calls=[
                        ToolCall(
                            id="tc1",
                            name="add_item",
                            arguments={"item": "banana"},
                        )
                    ],
                    stop_reason=StopReason.TOOL_USE,
                ),
                ModelResponse(
                    content="Done.",
                    stop_reason=StopReason.END_TURN,
                ),
            ]
        )

        deps = FakeDeps()
        agent = Agent(
            name="adder",
            model=model,
            tools=[add_item],
            max_iterations=5,
            empty_rounds_cap=2,
        )

        result = Runner.run_sync(agent, "Add banana", deps=deps)

        assert "banana" in deps.items
        assert result.iterations >= 2

    def test_finalization_stops_loop(self):
        """When deps.finalized is set, loop ends immediately."""

        @tool
        def finalize(ctx: RunContext[FakeDeps], summary: str) -> str:
            """Finalize.

            Args:
                summary: Result summary.
            """
            ctx.deps.finalized = {"summary": summary}
            return json.dumps({"ok": True})

        model = MockModel(
            [
                ModelResponse(
                    content="Finalizing.",
                    tool_calls=[
                        ToolCall(
                            id="tc1",
                            name="finalize",
                            arguments={"summary": "All done"},
                        )
                    ],
                    stop_reason=StopReason.TOOL_USE,
                ),
                # This response should never be reached
                ModelResponse(
                    content="Should not appear.",
                    stop_reason=StopReason.END_TURN,
                ),
            ]
        )

        deps = FakeDeps()
        agent = Agent(
            name="finalizer",
            model=model,
            tools=[finalize],
            max_iterations=10,
            empty_rounds_cap=3,
        )

        result = Runner.run_sync(agent, "Please finalize", deps=deps)

        assert deps.finalized == {"summary": "All done"}
        # Should stop after first iteration (finalized)
        assert result.iterations == 1
        assert model.call_count == 1

    def test_unknown_tool_handled(self):
        """Model calls a tool that doesn't exist — error result returned."""
        model = MockModel(
            [
                ModelResponse(
                    content="Calling missing tool.",
                    tool_calls=[
                        ToolCall(
                            id="tc1",
                            name="nonexistent_tool",
                            arguments={},
                        )
                    ],
                    stop_reason=StopReason.TOOL_USE,
                ),
                ModelResponse(
                    content="OK, I'll stop.",
                    stop_reason=StopReason.END_TURN,
                ),
            ]
        )

        agent = Agent(
            name="test",
            model=model,
            max_iterations=5,
            empty_rounds_cap=2,
        )

        result = Runner.run_sync(agent, "Do something")
        # Should complete without crashing
        assert result.iterations >= 1

    def test_empty_rounds_cap(self):
        """Loop ends after empty_rounds_cap consecutive rounds without tool calls."""
        model = MockModel(
            [
                ModelResponse(content="thinking...", stop_reason=StopReason.END_TURN),
                ModelResponse(
                    content="still thinking...", stop_reason=StopReason.END_TURN
                ),
            ]
        )

        agent = Agent(
            name="thinker",
            model=model,
            max_iterations=10,
            empty_rounds_cap=2,
        )

        result = Runner.run_sync(agent, "Think about it")
        # Should stop after 2 empty rounds
        assert result.iterations <= 3

    def test_max_iterations_cap(self):
        """Loop doesn't exceed max_iterations."""

        @tool
        def noop(ctx: RunContext[FakeDeps]) -> str:
            """Do nothing."""
            return '{"ok": true}'

        # Create responses that always call the tool (infinite loop scenario)
        responses = [
            ModelResponse(
                content=f"Call {i}",
                tool_calls=[ToolCall(id=f"tc{i}", name="noop", arguments={})],
                stop_reason=StopReason.TOOL_USE,
            )
            for i in range(20)
        ]

        deps = FakeDeps()
        model = MockModel(responses)
        agent = Agent(
            name="looper",
            model=model,
            tools=[noop],
            max_iterations=3,
            empty_rounds_cap=10,
        )

        result = Runner.run_sync(agent, "Loop forever", deps=deps)
        assert result.iterations <= 3

    def test_on_tool_result_callback(self):
        """on_tool_result callback is invoked after each tool execution."""

        @tool
        def ping() -> str:
            """Ping."""
            return '{"pong": true}'

        callback_log: list[tuple[str, str]] = []

        def on_result(tool_name: str, output: str, ctx: object) -> None:
            callback_log.append((tool_name, output))

        model = MockModel(
            [
                ModelResponse(
                    content="Pinging.",
                    tool_calls=[ToolCall(id="tc1", name="ping", arguments={})],
                    stop_reason=StopReason.TOOL_USE,
                ),
                ModelResponse(
                    content="Done.",
                    stop_reason=StopReason.END_TURN,
                ),
            ]
        )

        agent = Agent(
            name="pinger",
            model=model,
            tools=[ping],
            max_iterations=5,
            empty_rounds_cap=2,
        )

        Runner.run_sync(agent, "Ping", on_tool_result=on_result)

        assert len(callback_log) == 1
        assert callback_log[0][0] == "ping"
        assert "pong" in callback_log[0][1]

    def test_skills_loaded_into_system_prompt(self, tmp_path: Path):
        """Skills from skills_dir are loaded into the system prompt."""

        skill_file = tmp_path / "test_skill.md"
        skill_file.write_text(
            "---\nname: test_skill\n---\n\n# Test\nYou must always be polite.",
            encoding="utf-8",
        )

        model = MockModel(
            [ModelResponse(content="OK.", stop_reason=StopReason.END_TURN)]
        )

        agent = Agent(
            name="polite",
            model=model,
            instructions="Base instructions.",
            skills=["test_skill"],
            skills_dir=tmp_path,
            max_iterations=1,
            empty_rounds_cap=1,
        )

        Runner.run_sync(agent, "Hello")

        # The mock model should have received the skill body in the system prompt
        assert model.call_count >= 1
        assert "You must always be polite." in model.last_system

    def test_error_response_stops_loop(self):
        """Model returning StopReason.ERROR breaks the loop."""
        model = MockModel([ModelResponse(content="", stop_reason=StopReason.ERROR)])

        agent = Agent(
            name="test",
            model=model,
            max_iterations=5,
            empty_rounds_cap=3,
        )

        result = Runner.run_sync(agent, "Hello")
        assert model.call_count == 1

    def test_run_sync_works_when_called_from_async_context(self):
        """Runner.run_sync remains usable from sync bridge inside event loop."""
        model = MockModel(
            [ModelResponse(content="All done.", stop_reason=StopReason.END_TURN)]
        )
        agent = Agent(name="compat", model=model, max_iterations=3, empty_rounds_cap=1)

        async def _call_run_sync_from_loop() -> RunResult[Any]:
            return Runner.run_sync(agent, "Hello from loop")

        result = asyncio.run(_call_run_sync_from_loop())

        assert isinstance(result, RunResult)
        assert result.output == "All done."
        assert result.iterations == 1
        assert model.call_count == 1


# ================================================================== #
# Message pruning tests                                               #
# ================================================================== #


class TestMessagePruning:
    def test_pruning_preserves_first_and_last(self):
        """_prune_messages keeps first message + last N-1."""
        from app.ai.agent.runner import _prune_messages

        messages = [Message(role=Role.USER, content=f"msg{i}") for i in range(10)]
        pruned = _prune_messages(messages, max_turns=4)
        assert len(pruned) == 4
        assert pruned[0].content == "msg0"  # first preserved
        assert pruned[-1].content == "msg9"  # last preserved

    def test_no_pruning_under_limit(self):
        from app.ai.agent.runner import _prune_messages

        messages = [Message(role=Role.USER, content=f"msg{i}") for i in range(3)]
        pruned = _prune_messages(messages, max_turns=5)
        assert len(pruned) == 3


# ================================================================== #
# MCP types tests (no real server connection)                         #
# ================================================================== #


class TestMCPTypes:
    def test_mcp_server_stdio_factory(self):
        from app.ai.agent.mcp.client import MCPServer

        server = MCPServer.stdio("npx", args=["-y", "some-server"])
        assert server.transport == "stdio"
        assert server.command == "npx"
        assert server.args == ["-y", "some-server"]

    def test_mcp_server_http_factory(self):
        from app.ai.agent.mcp.client import MCPServer

        server = MCPServer.http("https://example.com/mcp", headers={"Auth": "token"})
        assert server.transport == "http"
        assert server.url == "https://example.com/mcp"
        assert server.headers == {"Auth": "token"}

    def test_mcp_tool_def(self):
        from app.ai.agent.mcp.types import MCPToolDef

        td = MCPToolDef(
            name="read_file",
            description="Read a file",
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "string"}},
            },
        )
        assert td.tool_def.name == "read_file"
        assert td.tool_def.parameters["properties"]["path"]["type"] == "string"


# ================================================================== #
# Model protocol tests                                                #
# ================================================================== #


class TestModelProtocol:
    def test_mock_model_is_protocol_compatible(self):
        """MockModel satisfies the Model protocol at runtime."""
        model = MockModel([])
        assert isinstance(model, Model)

    def test_model_response_defaults(self):
        r = ModelResponse()
        assert r.content == ""
        assert r.tool_calls == []
        assert r.stop_reason == StopReason.END_TURN
        assert r.raw is None

    def test_tool_def_structure(self):
        td = ToolDef(
            name="test",
            description="A test tool",
            parameters={"type": "object", "properties": {}},
        )
        assert td.name == "test"
        assert td.description == "A test tool"


# ================================================================== #
# Extraction tools tests (the rebuilt extraction tools)               #
# ================================================================== #


class TestExtractionTools:
    """Tests for the rebuilt extraction agent tools."""

    def test_all_tools_registered(self):
        from app.ai.agent_extraction.tools import ALL_EXTRACTION_TOOLS

        names = [t.name for t in ALL_EXTRACTION_TOOLS]
        assert "get_assignee_skills" in names
        assert "create_tasks" in names
        assert "recommend_assignees" in names
        assert "finalize_extraction" in names
        assert len(names) == 4

    def test_create_tasks_sets_deps(self):
        from app.ai.agent_extraction.tools import ExtractionDeps, create_tasks

        deps = ExtractionDeps(raw_text="")
        ctx = RunContext(deps=deps, agent_name="test")
        # Without a db session the tool should return an error, not crash
        result = json.loads(
            asyncio.run(
                create_tasks.execute(
                    ctx,
                    {
                        "source_summary": "テストソース",
                        "tasks": [
                            {
                                "title": "バグ修正",
                                "description": "テスト",
                                "priority": "high",
                            }
                        ],
                    },
                )
            )
        )
        assert result["ok"] is False
        assert "no_db_session" in result["error"]

    def test_create_tasks_description_mentions_english(self):
        """The create_tasks tool description mentions English language policy."""
        from app.ai.agent_extraction.tools import create_tasks

        assert "English" in create_tasks.description

    def test_agent_intro_is_english(self):
        """AGENT_INTRO_JA contains English extraction instructions."""
        from app.ai.agent_extraction.extraction_agent import AGENT_INTRO_JA

        assert "Extract" in AGENT_INTRO_JA
        assert "create_tasks" in AGENT_INTRO_JA

    def test_finalize_extraction_requires_result_source(self):
        from app.ai.agent_extraction.tools import ExtractionDeps, finalize_extraction

        deps = ExtractionDeps(raw_text="")
        ctx = RunContext(deps=deps, agent_name="test")

        result = json.loads(asyncio.run(finalize_extraction.execute(ctx, {})))
        assert result["ok"] is False
        assert "call create_tasks first" in result["error"]

    def test_finalize_extraction_persisted_mode_zero_tasks(self):
        from app.ai.agent_extraction.tools import ExtractionDeps, finalize_extraction

        deps = ExtractionDeps(raw_text="")
        deps.create_tasks_called = True
        deps.create_tasks_succeeded = True
        deps.source_summary = "抽出対象にタスクはありませんでした"
        ctx = RunContext(deps=deps, agent_name="test")

        result = json.loads(asyncio.run(finalize_extraction.execute(ctx, {})))
        assert result["ok"] is True
        assert result["mode"] == "persisted"
        assert result["tasks_finalized"] == 0
        assert deps.finalized is not None
        assert deps.finalized.source_summary == "抽出対象にタスクはありませんでした"
        assert deps.finalized.tasks == []

    def test_finalize_extraction_prefers_persisted_mode_after_create_tasks(self):
        from app.ai.agent_extraction.tools import ExtractionDeps, finalize_extraction

        deps = ExtractionDeps(raw_text="")
        deps.create_tasks_called = True
        deps.create_tasks_succeeded = True
        deps.source_summary = "Original persisted summary"
        ctx = RunContext(deps=deps, agent_name="test")

        result = json.loads(
            asyncio.run(
                finalize_extraction.execute(
                    ctx,
                    {"source_summary": "Updated persisted summary"},
                )
            )
        )

        assert result["ok"] is True
        assert result["mode"] == "persisted"
        assert result["tasks_finalized"] == 0
        assert deps.finalized is not None
        assert deps.finalized.source_summary == "Updated persisted summary"

    def test_finalize_extraction_direct_mode(self):
        from app.ai.agent_extraction.tools import ExtractionDeps, finalize_extraction

        deps = ExtractionDeps(raw_text="")
        ctx = RunContext(deps=deps, agent_name="test")

        payload = {
            "source_summary": "依頼からタスクを1件抽出しました",
            "tasks": [
                {
                    "title": "ログイン不具合を調査",
                    "priority": "high",
                    "confidence_score": 0.8,
                }
            ],
        }
        result = json.loads(asyncio.run(finalize_extraction.execute(ctx, payload)))
        assert result["ok"] is True
        assert result["mode"] == "direct"
        assert result["tasks_finalized"] == 1
        assert deps.finalized is not None
        assert deps.finalized.source_summary == "依頼からタスクを1件抽出しました"
        assert len(deps.finalized.tasks) == 1
        assert deps.finalized.tasks[0].title == "ログイン不具合を調査"


class TestGeminiModelClientConfig:
    def test_gemini_model_uses_api_key_client_by_default(self, monkeypatch):
        from app.ai.agent.models import gemini as gemini_module
        from app.ai.agent.models.gemini import GeminiModel

        calls = []

        def fake_client(**kwargs):
            calls.append(kwargs)
            return object()

        monkeypatch.setattr(gemini_module.genai, "Client", fake_client)

        GeminiModel(api_key="test-key", model="gemini-test")

        assert calls == [{"api_key": "test-key"}]

    def test_gemini_model_uses_vertexai_client_when_enabled(self, monkeypatch):
        from app.ai.agent.models import gemini as gemini_module
        from app.ai.agent.models.gemini import GeminiModel

        calls = []

        def fake_client(**kwargs):
            calls.append(kwargs)
            return object()

        monkeypatch.setattr(gemini_module.genai, "Client", fake_client)

        GeminiModel(
            model="gemini-test",
            vertexai=True,
            project="my-project",
            location="us-central1",
        )

        assert calls == [
            {"vertexai": True, "project": "my-project", "location": "us-central1"}
        ]

    def test_gemini_model_uses_vertexai_api_key_mode(self, monkeypatch):
        from app.ai.agent.models import gemini as gemini_module
        from app.ai.agent.models.gemini import GeminiModel

        calls = []

        def fake_client(**kwargs):
            calls.append(kwargs)
            return object()

        monkeypatch.setattr(gemini_module.genai, "Client", fake_client)

        GeminiModel(api_key="vertex-key", model="gemini-test", vertexai=True)

        assert calls == [{"vertexai": True, "api_key": "vertex-key"}]
