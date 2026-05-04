"""app.ai.postprocessor — Pure post-processing functions for extracted tasks.

Exports: validate_tasks, deduplicate

Zero IO — pure functions only.
"""
from app.ai.gemini_client import ExtractedTask
from rapidfuzz import fuzz, utils as rfuzz_utils


def validate_tasks(tasks: list[ExtractedTask]) -> list[ExtractedTask]:
    """Filter out tasks with empty or whitespace-only titles."""
    return [t for t in tasks if t.title and t.title.strip()]


def deduplicate(tasks: list[ExtractedTask], threshold: int = 85) -> list[ExtractedTask]:
    """Remove duplicate tasks using exact match then fuzzy token_set_ratio.

    Keeps first occurrence. Threshold 85 catches stopword variants
    ('Fix login bug' vs 'Fix the login bug') while preserving distinct tasks.
    """
    seen_normalized: list[str] = []
    result: list[ExtractedTask] = []
    for task in tasks:
        norm = rfuzz_utils.default_process(task.title)
        if norm in seen_normalized:
            continue  # exact duplicate (fast path)
        if any(fuzz.token_set_ratio(norm, s) >= threshold for s in seen_normalized):
            continue  # fuzzy duplicate
        seen_normalized.append(norm)
        result.append(task)
    return result
