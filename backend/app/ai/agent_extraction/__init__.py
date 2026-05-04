"""Autonomous tool-calling agent for task extraction.

Built on the ``app.ai.agent`` framework (Agent + Runner + @tool).
"""

from app.ai.agent_extraction.extraction_agent import (
    UserPrompt,
    run_autonomous_extraction_sync,
)

__all__ = ["UserPrompt", "run_autonomous_extraction_sync"]
