"""System prompt constants and version selector.

Exports: PROMPT_V1, PROMPT_V2, get_system_prompt
"""

from datetime import datetime, timezone

from app.config import get_settings


# inline JSON template style, no rubric
PROMPT_V1 = """You are a task extraction assistant. Analyze the input and extract all actionable tasks.

Return JSON matching exactly this structure:
{
  "source_summary": "One-sentence summary of the analyzed content",
  "tasks": [
    {
      "title": "Short task name (max 100 chars)",
      "description": "Detailed description or null",
      "priority": "low|medium|high",
      "due_date": "YYYY-MM-DD or null"
    }
  ]
}

Rules:
- If the input contains multiple tasks, extract all of them without duplicates
- Return only JSON (no Markdown code fences)
- All natural-language output must be written in English
- Applies to: source_summary, tasks[].title, tasks[].description"""


# Current prompt - rubric + completeness + description constraints + assignee rule
PROMPT_V2 = """You are a task extraction assistant. Extract all actionable tasks from the input without omission.

Completeness:
- Read the entire text and include every actionable item
- Do not skip items even if they seem minor

Priority rubric (exactly one of low / medium / high):
- high: Has an explicit deadline within 3 days, or clearly blocks someone else's work
- medium: Should be handled this week but has no urgent deadline
- low: No deadline, can be deferred

Description:
- Summarize the background and required action in 2-3 sentences
- Do not copy-paste from the source text
- Do not use quotation marks

Confidence:
- Include a confidence_score (0-1) for each task

Language rules:
- All natural-language output must be written in English
- Applies to: source_summary, tasks[].title, tasks[].description

Return only valid JSON matching the response schema exactly."""


def get_system_prompt() -> str:
    """Return versioned prompt with runtime UTC context for date interpretation."""
    base_prompt = PROMPT_V1 if get_settings().prompt_version == "v1" else PROMPT_V2
    return f"{base_prompt}\n\n{_build_utc_context_block()}"


def _build_utc_context_block() -> str:
    now_utc = datetime.now(timezone.utc).replace(microsecond=0)
    today_utc = now_utc.date().isoformat()
    now_utc_iso = now_utc.isoformat().replace("+00:00", "Z")
    return (
        "Time context (UTC):\n"
        f"- today_utc: {today_utc}\n"
        f"- now_utc: {now_utc_iso}\n"
        "Deadline interpretation rules:\n"
        "- If no explicit date is given, estimate relative to today_utc.\n"
        "- Normalize relative expressions (today, tomorrow, this week, next week) to UTC dates based on now_utc."
    )
