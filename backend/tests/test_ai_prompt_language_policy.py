import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")

from app.ai.agent_extraction.extraction_agent import AGENT_INTRO_JA
from app.ai.agent_extraction.tools import ALL_EXTRACTION_TOOLS


def test_autonomous_agent_intro_is_english():
    assert "Extract actionable tasks" in AGENT_INTRO_JA
    assert "create_tasks" in AGENT_INTRO_JA
    assert "finalize_extraction" in AGENT_INTRO_JA


def test_create_tasks_tool_mentions_english_policy():
    tool = next(t for t in ALL_EXTRACTION_TOOLS if t.name == "create_tasks")
    assert "English" in tool.description
