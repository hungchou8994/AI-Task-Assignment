"""Unit tests for app/ai/ sub-modules — EXT-07.

Tests cover: preprocessor.strip_html, prompts.get_system_prompt, postprocessor.validate_tasks.
These will fail RED until app/ai/ package is created.
Run: docker compose exec api python -m pytest tests/test_ai_modules.py -x -q
"""

import pytest
from app.ai.preprocessor import strip_html
from app.ai.prompts import get_system_prompt
from app.ai.postprocessor import validate_tasks
from app.ai.gemini_client import ExtractedTask
from app.config import get_settings


# --- strip_html tests ---


def test_strip_html():
    """Script blocks and HTML tags are removed, leaving plain text."""
    result = strip_html("<script>js()</script><p>Hello <b>World</b></p>")
    assert result == "Hello World"


def test_strip_html_style():
    """Style blocks (including their content) are stripped, leaving plain text."""
    result = strip_html("<style>.x{}</style><div>content</div>")
    assert result == "content"


def test_strip_html_collapses_whitespace():
    """Multi-space/newline HTML produces single-space clean text."""
    result = strip_html("<p>Hello   \n  World</p>")
    assert result == "Hello World"


# --- get_system_prompt tests ---


def test_prompt_v2_default():
    """Default (no env var) returns PROMPT_V2 with English language policy."""
    prompt = get_system_prompt()
    assert "English" in prompt
    assert "source_summary" in prompt
    assert "tasks" in prompt


def test_prompt_v1_env_var(monkeypatch):
    """PROMPT_VERSION=v1 returns PROMPT_V1 which still requires English output."""
    get_settings.cache_clear()
    monkeypatch.setenv("PROMPT_VERSION", "v1")
    try:
        prompt = get_system_prompt()
        assert "English" in prompt
    finally:
        get_settings.cache_clear()  # restore for subsequent tests


# --- validate_tasks tests ---


def test_validate_tasks_filters_empty():
    """Tasks with empty title are filtered out."""
    tasks = [ExtractedTask(title="", priority="low")]
    result = validate_tasks(tasks)
    assert result == []


def test_validate_tasks_keeps_valid():
    """Tasks with non-empty title are kept."""
    tasks = [ExtractedTask(title="Fix bug", priority="low")]
    result = validate_tasks(tasks)
    assert len(result) == 1
