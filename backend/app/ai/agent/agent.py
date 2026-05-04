"""Agent — declarative configuration for an autonomous agent.

An Agent is pure config.  It declares *what* the agent is (name, instructions,
tools, model, limits) but does *nothing* by itself.  The ``Runner`` takes an
Agent and executes it.

Inspired by OpenAI Agents SDK: "Agent = config, Runner = engine."
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from app.ai.agent.model import Model
from app.ai.agent.skills import SkillSource
from app.ai.agent.tool import Tool


@dataclass
class Agent:
    """Declarative agent configuration.

    Attributes:
        name:              Human-readable agent name (used in logs and events).
        instructions:      Base system prompt string.
        skills:            Skill sources loaded at run time and prepended to
                           the system prompt.  Each entry can be a skill name
                           (resolved from ``skills_dir``), a ``Path`` to a
                           markdown file, or a ``Callable[[], str]``.
        skills_dir:        Directory where named skills are looked up.
        tools:             Local ``Tool`` instances registered with ``@tool``.
        mcp_servers:       MCP server configs (tools discovered at run time).
        model:             LLM ``Model`` instance or a factory callable.
        max_iterations:    Hard cap on think→act→observe iterations.
        max_context_turns: Max conversation turns before pruning.
        empty_rounds_cap:  Consecutive rounds without tool calls before
                           fallback / nudge.
        temperature:       Sampling temperature sent to the model.
        max_tokens:        Max output tokens per model call.
        mutating_tools:    Tool names that break the loop detector's
                           read-only streak counter.
    """

    name: str = "agent"
    instructions: str = ""
    skills: list[SkillSource] = field(default_factory=list)
    skills_dir: Path | None = None
    tools: list[Tool] = field(default_factory=list)
    mcp_servers: list[Any] = field(default_factory=list)  # MCPServer instances
    model: Model | Callable[[], Model] | None = None
    max_iterations: int = 20
    max_context_turns: int = 28
    empty_rounds_cap: int = 3
    temperature: float = 0.2
    max_tokens: int = 8192
    mutating_tools: set[str] | None = None

    def get_model(self) -> Model:
        """Resolve the model, calling the factory if needed."""
        if self.model is None:
            raise ValueError(
                f"Agent {self.name!r} has no model configured. "
                "Pass a Model instance or factory to Agent(model=...)."
            )
        if callable(self.model) and not isinstance(self.model, Model):
            self.model = self.model()
        return self.model  # type: ignore[return-value]
