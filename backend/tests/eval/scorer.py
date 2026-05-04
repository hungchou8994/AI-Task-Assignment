"""Extraction quality scorer — pure metric functions, no Gemini API required.

Exports: completeness_score, precision_score, priority_accuracy, dedup_rate

All functions are pure (no IO) and can be imported without any API keys.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from rapidfuzz import fuzz

if TYPE_CHECKING:
    from app.ai.gemini_client import ExtractedTask

FUZZY_THRESHOLD = 80


def completeness_score(extracted_titles: list[str], expected_titles: list[str]) -> float:
    """Fraction of expected tasks found in extraction (fuzzy token_set_ratio >= 80).

    Returns 1.0 when expected_titles is empty (negative case: nothing expected).
    """
    if not expected_titles:
        return 1.0
    found = sum(
        1 for exp in expected_titles
        if any(fuzz.token_set_ratio(exp, ext) >= FUZZY_THRESHOLD for ext in extracted_titles)
    )
    return found / len(expected_titles)


def precision_score(extracted_titles: list[str], expected_titles: list[str]) -> float:
    """Fraction of extracted tasks matching a known expected task (no hallucinations).

    Returns 1.0 when extracted_titles is empty (nothing extracted, nothing wrong).
    """
    if not extracted_titles:
        return 1.0
    correct = sum(
        1 for ext in extracted_titles
        if any(fuzz.token_set_ratio(ext, exp) >= FUZZY_THRESHOLD for exp in expected_titles)
    )
    return correct / len(extracted_titles)


def priority_accuracy(extracted: list, expected_priorities: dict[str, int]) -> float:
    """Fraction of tasks with correctly classified priority level.

    Compares count of each priority level in extracted vs expected distribution.
    Returns 1.0 when expected_priorities is empty or extracted is empty.
    """
    if not expected_priorities or not extracted:
        return 1.0
    total = sum(expected_priorities.values())
    if total == 0:
        return 1.0
    actual_counts: dict[str, int] = {"high": 0, "medium": 0, "low": 0}
    for t in extracted:
        actual_counts[t.priority] = actual_counts.get(t.priority, 0) + 1
    correct = sum(min(actual_counts.get(k, 0), v) for k, v in expected_priorities.items())
    return correct / total


def dedup_rate(tasks_before: list, tasks_after: list) -> float:
    """Fraction of tasks surviving deduplication (1.0 = no duplicates found).

    Returns 1.0 when tasks_before is empty.
    """
    if not tasks_before:
        return 1.0
    return len(tasks_after) / len(tasks_before)
