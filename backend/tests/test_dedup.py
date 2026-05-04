"""Unit tests for deduplicate() — EXT-06.

Pure function tests: no HTTP client, no DB, no mocking required.
Run: docker compose exec api python -m pytest tests/test_dedup.py -x -q
"""
import pytest
from app.ai.postprocessor import deduplicate
from app.ai.gemini_client import ExtractedTask


def make_task(title: str, priority: str = "medium") -> ExtractedTask:
    """Helper: create a minimal ExtractedTask with the given title."""
    return ExtractedTask(title=title, priority=priority)


class TestDeduplicateExact:
    def test_exact_duplicate_removed(self):
        """Two tasks with identical titles → only one survives."""
        tasks = [make_task("Fix login bug"), make_task("Fix login bug")]
        result = deduplicate(tasks)
        assert len(result) == 1
        assert result[0].title == "Fix login bug"

    def test_case_insensitive_exact_match(self):
        """Exact match is case-insensitive (utils.default_process normalizes)."""
        tasks = [make_task("Fix Login Bug"), make_task("fix login bug")]
        result = deduplicate(tasks)
        assert len(result) == 1


class TestDeduplicateFuzzy:
    def test_near_duplicate_removed(self):
        """'Fix login bug' and 'Fix the login bug' are fuzzy-duplicate (token_set_ratio=100)."""
        tasks = [make_task("Fix login bug"), make_task("Fix the login bug")]
        result = deduplicate(tasks)
        assert len(result) == 1

    def test_distinct_tasks_both_kept(self):
        """'Fix login bug' and 'Fix signup bug' are distinct (token_set_ratio ~67 < 85)."""
        tasks = [make_task("Fix login bug"), make_task("Fix signup bug")]
        result = deduplicate(tasks)
        assert len(result) == 2

    def test_first_occurrence_kept(self):
        """When a duplicate is found, the FIRST occurrence is kept."""
        tasks = [make_task("Deploy to staging"), make_task("Deploy to the staging environment")]
        result = deduplicate(tasks)
        assert len(result) == 1
        assert result[0].title == "Deploy to staging"


class TestDeduplicateEdgeCases:
    def test_empty_list(self):
        """Empty input → empty output."""
        assert deduplicate([]) == []

    def test_single_item(self):
        """Single task → returned unchanged."""
        tasks = [make_task("Fix login bug")]
        result = deduplicate(tasks)
        assert len(result) == 1
        assert result[0].title == "Fix login bug"

    def test_preserves_task_attributes(self):
        """Non-duplicate tasks retain all their attributes."""
        tasks = [
            make_task("Fix login bug", priority="high"),
            make_task("Write tests", priority="low"),
        ]
        result = deduplicate(tasks)
        assert len(result) == 2
        assert result[0].priority == "high"
        assert result[1].priority == "low"
