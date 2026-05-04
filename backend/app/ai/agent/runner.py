"""Runner — the agent execution engine.

The Runner owns the think → act → observe loop.  It takes an ``Agent``
(pure config) and executes it against a prompt and dependencies.

Design: inspired by OpenAI Agents SDK (Runner.run / Runner.run_sync)
and Anthropic's "agents are just LLMs in a loop calling tools" philosophy.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from app.ai.agent.agent import Agent
from app.ai.agent.context import RunContext
from app.ai.agent.event_emitter import EventEmitter, NullEmitter
from app.ai.agent.loop_detector import LoopAction, ToolLoopDetector
from app.ai.agent.model import (
    Message,
    ModelResponse,
    Role,
    StopReason,
    StreamEventKind,
    ToolCall,
    ToolDef,
    ToolResult,
)
from app.ai.agent.skills import resolve_skill_sources
from app.ai.agent.tool import Tool, scrub_tool_output

logger = logging.getLogger(__name__)

# Tiny pacing for streamed deltas so bursty provider chunks feel like
# continuous streaming in the UI.
_MIN_STREAM_DELTA_INTERVAL_SECONDS = 0.02

DepsT = TypeVar("DepsT")


@dataclass
class RunResult(Generic[DepsT]):
    """Outcome of a Runner.run() invocation."""

    output: str = ""
    messages: list[Message] = field(default_factory=list)
    iterations: int = 0
    final_response: ModelResponse | None = None
    context: RunContext[DepsT] | None = None


class Runner:
    """Agent execution engine — owns the think → act → observe loop."""

    @staticmethod
    async def run(
        agent: Agent,
        prompt: str,
        *,
        deps: Any = None,
        emitter: EventEmitter | None = None,
        on_tool_result: Any | None = None,
    ) -> RunResult[Any]:
        """Execute the agent loop asynchronously.

        Args:
            agent:          Agent config.
            prompt:         User prompt / initial message.
            deps:           Dependencies injected into tools via RunContext.
            emitter:        Optional event emitter for SSE streaming.
            on_tool_result: Optional callback ``(tool_name, result_str, ctx) -> None``
                            called after each tool execution.  Useful for
                            detecting "finalize" tools and setting state.

        Returns:
            RunResult with the final output and conversation history.
        """
        emitter = emitter or NullEmitter()
        model = agent.get_model()

        # Build system prompt: instructions + skills
        system_prompt = _build_system_prompt(agent)

        # Collect tool definitions (local + MCP)
        tools, tool_registry = await _collect_tools(agent)

        # Build initial context
        ctx: RunContext[Any] = RunContext(
            deps=deps,
            agent_name=agent.name,
        )

        # Conversation history
        messages: list[Message] = [
            Message(role=Role.USER, content=prompt),
        ]

        detector = ToolLoopDetector(
            mutating_tools=agent.mutating_tools or {"finalize_extraction"},
        )
        empty_rounds = 0

        emitter.emit("loop_started", message=f"Agent '{agent.name}' loop started")

        for iteration in range(agent.max_iterations):
            loop_iter = iteration + 1
            ctx.iteration = loop_iter
            messages = _prune_messages(messages, agent.max_context_turns)

            logger.debug(
                "[%s] iteration=%d messages=%d",
                agent.name,
                loop_iter,
                len(messages),
            )
            emitter.emit(
                "iteration_started",
                iteration=loop_iter,
                message=f"Starting iteration {loop_iter}",
            )

            # --- Stream tokens from the model ---
            response: ModelResponse | None = None

            # Check if the model supports streaming
            _has_stream = hasattr(model, "generate_stream") and callable(
                getattr(model, "generate_stream", None)
            )

            if _has_stream:
                # Emit a stable id for the thinking/text bubble so the
                # frontend can accumulate deltas into the same UI element.
                import uuid as _uuid

                thinking_stream_id = str(_uuid.uuid4())
                text_stream_id = str(_uuid.uuid4())
                emitted_thinking_start = False
                emitted_text_start = False
                last_delta_emit_at = 0.0

                async def _pace_delta_emission() -> None:
                    nonlocal last_delta_emit_at
                    now = asyncio.get_running_loop().time()
                    elapsed = now - last_delta_emit_at
                    wait_for = _MIN_STREAM_DELTA_INTERVAL_SECONDS - elapsed
                    if wait_for > 0:
                        await asyncio.sleep(wait_for)
                    last_delta_emit_at = asyncio.get_running_loop().time()

                async for event in model.generate_stream(
                    messages,
                    tools,
                    system=system_prompt,
                    temperature=agent.temperature,
                    max_tokens=agent.max_tokens,
                ):
                    if event.kind == StreamEventKind.THINKING_DELTA:
                        if not emitted_thinking_start:
                            emitted_thinking_start = True
                            emitter.emit(
                                "thinking_start",
                                iteration=loop_iter,
                                message="",
                                metadata={"stream_id": thinking_stream_id},
                            )
                        await _pace_delta_emission()
                        emitter.emit(
                            "thinking_delta",
                            iteration=loop_iter,
                            message=event.delta,
                            metadata={"stream_id": thinking_stream_id},
                        )

                    elif event.kind == StreamEventKind.TEXT_DELTA:
                        if not emitted_text_start:
                            emitted_text_start = True
                            emitter.emit(
                                "text_start",
                                iteration=loop_iter,
                                message="",
                                metadata={"stream_id": text_stream_id},
                            )
                        await _pace_delta_emission()
                        emitter.emit(
                            "text_delta",
                            iteration=loop_iter,
                            message=event.delta,
                            metadata={"stream_id": text_stream_id},
                        )

                    elif event.kind == StreamEventKind.FINISH:
                        response = event.response

                # Emit end markers so the frontend knows streaming is done
                if emitted_thinking_start:
                    emitter.emit(
                        "thinking_end",
                        iteration=loop_iter,
                        metadata={
                            "stream_id": thinking_stream_id,
                            "usage": response.usage
                            if response and response.usage
                            else None,
                        },
                    )
                if emitted_text_start:
                    emitter.emit(
                        "text_end",
                        iteration=loop_iter,
                        metadata={"stream_id": text_stream_id},
                    )
            else:
                # Fallback: non-streaming model
                response = await model.generate(
                    messages,
                    tools,
                    system=system_prompt,
                    temperature=agent.temperature,
                    max_tokens=agent.max_tokens,
                )

                # Emit thinking / reasoning as before (single-shot)
                if response.thinking:
                    emitter.emit(
                        "thinking",
                        iteration=loop_iter,
                        message=response.thinking,
                        metadata={"usage": response.usage} if response.usage else None,
                    )
                if response.content and response.tool_calls:
                    emitter.emit(
                        "reasoning",
                        iteration=loop_iter,
                        message=response.content,
                    )

            if response is None:
                emitter.emit(
                    "error",
                    iteration=loop_iter,
                    message="Model returned no response",
                )
                break

            if response.stop_reason == StopReason.ERROR:
                err_msg = response.content.strip() if response.content else ""
                emitter.emit(
                    "error",
                    iteration=loop_iter,
                    message=err_msg or "Model returned no content",
                )
                break

            # --- Append assistant message ---
            assistant_msg = Message(
                role=Role.ASSISTANT,
                content=response.content,
                tool_calls=response.tool_calls,
                thought_signature=response.thought_signature,
            )
            messages.append(assistant_msg)

            # --- Handle tool calls ---
            if response.tool_calls:
                empty_rounds = 0
                tool_msg, nudge = await _execute_tool_calls(
                    response.tool_calls,
                    tool_registry,
                    ctx,
                    detector,
                    emitter,
                    loop_iter,
                    on_tool_result,
                )
                messages.append(tool_msg)

                if nudge:
                    messages.append(Message(role=Role.USER, content=nudge))

                # Check if the caller set a "done" flag via on_tool_result
                if _is_finalized(ctx):
                    emitter.emit(
                        "finalized",
                        iteration=loop_iter,
                        message="Agent finalized",
                    )
                    return RunResult(
                        output=response.content,
                        messages=messages,
                        iterations=loop_iter,
                        final_response=response,
                        context=ctx,
                    )

            else:
                # No tool calls this round
                empty_rounds += 1
                emitter.emit(
                    "no_tool_calls",
                    iteration=loop_iter,
                    message=f"No tool calls ({empty_rounds}/{agent.empty_rounds_cap})",
                )

                if empty_rounds >= agent.empty_rounds_cap:
                    emitter.emit(
                        "max_empty_rounds",
                        iteration=loop_iter,
                        message="Too many rounds without tool calls",
                    )
                    break

                # Nudge the model to use tools or finalize
                messages.append(
                    Message(
                        role=Role.USER,
                        content=(
                            "No tools were called. Please use the available tools "
                            "to make progress, or finalize your result."
                        ),
                    )
                )

        emitter.emit("loop_ended", message="Agent loop ended")

        return RunResult(
            output=response.content if response else "",
            messages=messages,
            iterations=min(iteration + 1, agent.max_iterations)
            if "iteration" in dir()
            else 0,
            final_response=response if "response" in dir() else None,
            context=ctx,
        )

    @staticmethod
    def run_sync(
        agent: Agent,
        prompt: str,
        **kwargs: Any,
    ) -> RunResult[Any]:
        """Synchronous wrapper around ``run()``.

        Safe to call from a sync context (e.g. background threads).
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # We're inside an async context — create a new event loop in a thread
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, Runner.run(agent, prompt, **kwargs))
                return future.result()
        else:
            return asyncio.run(Runner.run(agent, prompt, **kwargs))


# ------------------------------------------------------------------ #
# Internal helpers                                                     #
# ------------------------------------------------------------------ #


def _build_system_prompt(agent: Agent) -> str:
    """Assemble the full system prompt: instructions + loaded skills."""
    parts: list[str] = []

    if agent.instructions:
        parts.append(agent.instructions)

    if agent.skills:
        skills_text = resolve_skill_sources(agent.skills, skills_dir=agent.skills_dir)
        if skills_text:
            parts.append(skills_text)

    return "\n\n".join(parts)


async def _collect_tools(agent: Agent) -> tuple[list[ToolDef], dict[str, Tool]]:
    """Collect tool definitions from local tools + MCP servers.

    Returns (list of ToolDefs for the model, dict of name→Tool for execution).
    """
    tool_defs: list[ToolDef] = []
    registry: dict[str, Tool] = {}

    # Local tools
    for t in agent.tools:
        tool_defs.append(t.tool_def)
        registry[t.name] = t

    # MCP tools (lazy import to avoid hard dependency)
    for server in agent.mcp_servers:
        try:
            mcp_tools = await server.list_tools()
            for mt in mcp_tools:
                tool_defs.append(mt.tool_def)
                registry[mt.name] = mt
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to list MCP tools from %s: %s", server, exc)

    return tool_defs, registry


def _prune_messages(messages: list[Message], max_turns: int) -> list[Message]:
    """Keep the first message + last (max_turns - 1) messages."""
    if len(messages) <= max_turns:
        return messages
    return [messages[0]] + messages[-(max_turns - 1) :]


async def _execute_tool_calls(
    tool_calls: list[ToolCall],
    registry: dict[str, Tool],
    ctx: RunContext[Any],
    detector: ToolLoopDetector,
    emitter: EventEmitter,
    iteration: int,
    on_tool_result: Any | None,
) -> tuple[Message, str | None]:
    """Execute all tool calls and return (tool_results_message, optional_nudge)."""
    results: list[ToolResult] = []
    nudge: str | None = None

    for tc in tool_calls:
        emitter.emit(
            "tool_call",
            iteration=iteration,
            tool_name=tc.name,
            message=f"Calling tool: {tc.name}",
            metadata={"call_id": tc.id, "arguments": tc.arguments},
        )

        tool = registry.get(tc.name)
        if tool is None:
            error_msg = json.dumps({"error": f"unknown_tool:{tc.name}"})
            results.append(
                ToolResult(
                    call_id=tc.id,
                    name=tc.name,
                    content=error_msg,
                    is_error=True,
                )
            )
            emitter.emit(
                "tool_error",
                iteration=iteration,
                tool_name=tc.name,
                message=f"Unknown tool: {tc.name}",
                output=error_msg,
                metadata={"call_id": tc.id},
            )
            continue

        try:
            output = await tool.execute(ctx, tc.arguments)
        except Exception as exc:  # noqa: BLE001
            logger.exception("[%s] tool crashed: %s", ctx.agent_name, tc.name)
            output = json.dumps({"error": str(exc)}, ensure_ascii=False)
            emitter.emit(
                "tool_error",
                iteration=iteration,
                tool_name=tc.name,
                message=str(exc),
                output=output,
                metadata={"call_id": tc.id},
            )

        output = scrub_tool_output(output)
        emitter.emit(
            "tool_result",
            iteration=iteration,
            tool_name=tc.name,
            output=output,
            metadata={"call_id": tc.id},
        )

        # Notify caller (e.g., to detect finalize_extraction)
        if on_tool_result is not None:
            try:
                on_tool_result(tc.name, output, ctx)
            except Exception:  # noqa: BLE001
                pass

        # Loop detection
        args_json = json.dumps(tc.arguments, sort_keys=True, ensure_ascii=False)
        action = detector.record_tool_call(tc.name, args_json, output)

        if action == LoopAction.STOP:
            nudge = ToolLoopDetector.stop_message()
            emitter.emit(
                "loop_guard_stop",
                iteration=iteration,
                message=nudge,
            )
        elif action == LoopAction.WARN and nudge is None:
            nudge = ToolLoopDetector.warn_message()
            emitter.emit(
                "loop_guard_warn",
                iteration=iteration,
                message=nudge,
            )

        results.append(
            ToolResult(
                call_id=tc.id,
                name=tc.name,
                content=output,
            )
        )

    tool_msg = Message(role=Role.TOOL, tool_results=results)
    return tool_msg, nudge


def _is_finalized(ctx: RunContext[Any]) -> bool:
    """Check if the deps object has a ``finalized`` attribute set to a truthy value."""
    deps = ctx.deps
    if deps is None:
        return False
    return bool(getattr(deps, "finalized", None))
