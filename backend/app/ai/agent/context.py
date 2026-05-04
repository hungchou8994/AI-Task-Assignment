"""RunContext — typed dependency injection for tool handlers.

Pattern inspired by Pydantic AI: tools receive `RunContext[Deps]` as their
first argument.  The context is injected automatically by the runner; the LLM
never sees it in the tool schema.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

DepsT = TypeVar("DepsT")


@dataclass
class RunContext(Generic[DepsT]):
    """Immutable (by convention) context injected into every tool call.

    Attributes:
        deps:       User-supplied dependencies (DB session, config, etc.).
        agent_name: Name of the agent that owns this run.
        iteration:  Current loop iteration (1-indexed).
        usage:      Mutable dict for tracking token usage, etc.
    """

    deps: DepsT
    agent_name: str = ""
    iteration: int = 0
    usage: dict[str, Any] = field(default_factory=dict)
