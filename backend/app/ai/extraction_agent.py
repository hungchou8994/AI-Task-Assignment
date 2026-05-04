"""Public entrypoints for advanced extraction modes.

`app.ai.agent_extraction` (think → act → observe), built on the
`app.ai.agent` framework (Agent + Runner + @tool).
"""

from __future__ import annotations

from app.ai.agent_extraction.extraction_agent import (
    AgentRunResult,
    UserPrompt,
    run_autonomous_extraction_async,
    run_autonomous_extraction_sync,
)

__all__ = [
    "AgentRunResult",
    "UserPrompt",
    "run_autonomous_extraction_async",
    "run_autonomous_extraction_sync",
]
