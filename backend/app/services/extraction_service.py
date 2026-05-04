"""Extraction service — orchestrates AI task extraction and persistence.

The agent loop (via run_autonomous_extraction_sync) now handles persistence
directly through the create_tasks and recommend_assignees tools.  This service
is responsible for:
  1. Preprocessing raw input into a prompt.
  2. Invoking the agent loop.
  3. Building the ExtractTasksResult from the agent's output.
"""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from app.ai.extraction_agent import UserPrompt, run_autonomous_extraction_async
from app.ai.preprocessor import ParsedEmail, fetch_url, preprocess, strip_html
from app.ai.prompts import get_system_prompt
from app.config import get_settings
from app.schemas import (
    AssigneeRecommendationItem,
    ExtractedTaskItem,
    ExtractionOutcome,
    ExtractTasksCommand,
    ExtractTasksResult,
)
from app.services.candidate_provenance_service import compute_prompt_template_hash
from app.services.memory_audit_service import MemoryAuditService
from app.services.memory_context_builder import build_extraction_memory_bundle

logger = logging.getLogger(__name__)
_memory_audit_service = MemoryAuditService()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def extract_tasks(
    db: Session, command: ExtractTasksCommand
) -> ExtractTasksResult:
    """Run the full extraction pipeline: extract → recommend → persist.

    Persistence happens inside the agent loop via create_tasks and
    recommend_assignees tools.  This function preprocesses the input,
    invokes the agent, and wraps the result.
    """
    raw_content = preprocess(command.source_type, command.content)
    user_prompt = _build_user_prompt(raw_content)
    system_prompt = get_system_prompt()
    settings = get_settings()

    if settings.memory_enabled:
        memory_bundle = None
        try:
            memory_bundle = build_extraction_memory_bundle(db, command)
            if memory_bundle.scope:
                _memory_audit_service.log_memory_search(
                    db,
                    scope=memory_bundle.scope,
                    actor_type="system",
                    actor_id=None,
                    query=memory_bundle.query,
                    result_count=memory_bundle.result_count,
                    latency_ms=memory_bundle.latency_ms,
                    status="ok",
                    metadata={"action": "extraction"},
                )
            if memory_bundle.context:
                user_prompt = _append_memory_context(user_prompt, memory_bundle.context)
                if memory_bundle.scope:
                    _memory_audit_service.log_memory_injection(
                        db,
                        scope=memory_bundle.scope,
                        actor_type="system",
                        actor_id=None,
                        query=memory_bundle.query,
                        result_count=memory_bundle.result_count,
                        status="ok",
                        metadata={
                            "action": "extraction",
                            "context_chars": len(memory_bundle.context),
                        },
                    )
        except Exception as exc:  # fail-open path
            logger.warning(
                "memory retrieval failed; continuing without memory: %s", exc
            )
            _memory_audit_service.log_memory_error(
                db,
                scope=(memory_bundle.scope if memory_bundle else None),
                action="search",
                actor_type="system",
                actor_id=None,
                query=(memory_bundle.query if memory_bundle else command.content),
                status="error",
                metadata={"error": str(exc)[:500], "phase": "extraction"},
            )

    source_excerpt = _derive_source_excerpt(raw_content)
    raw_content_str = (
        command.content if isinstance(command.content, str) else str(command.content)
    )
    source_uri: str | None = None
    source_payload: dict[str, str] = {}
    if command.source_type == "text":
        source_payload = {"raw_text": command.content}
    elif command.source_type == "url":
        source_uri = command.content
        if isinstance(raw_content, str):
            source_payload = {"fetched_text": raw_content}

    content_hash = hashlib.sha256(
        raw_content_str.encode("utf-8", errors="replace")
    ).hexdigest()
    prompt_template_hash = compute_prompt_template_hash(system_prompt)
    model_version = (
        settings.openai_model
        if settings.ai_agent_provider == "openai"
        else settings.gemini_model
    )

    started_at = time.perf_counter()
    agent_result = await run_autonomous_extraction_async(
        user_prompt,
        system_prompt,
        db=db,
        project_id=command.project_id,
        job_id=command.job_id,
        source_type=command.source_type,
        source_excerpt=source_excerpt,
        source_uri=source_uri,
        source_payload=source_payload,
        content_hash=content_hash,
        model_version=model_version,
        prompt_template_hash=prompt_template_hash,
    )
    latency_ms = int((time.perf_counter() - started_at) * 1000)  # noqa: F841 (for future use)

    outcome = ExtractionOutcome(
        source_summary=agent_result.finalized.source_summary,
        tasks=tuple(
            ExtractedTaskItem(
                title=item.title,
                description=item.description,
                priority=item.priority,
                due_date=_parse_due_date(item.due_date),
                confidence_score=max(0.0, min(1.0, item.confidence_score)),
                assignee_recommendations=tuple(
                    AssigneeRecommendationItem(
                        rank=r.rank,
                        person_id=r.person_id,
                        name=r.name,
                        confidence_score=r.confidence_score,
                        reasoning=r.reasoning,
                    )
                    for r in (item.assignee_recommendations or [])
                ),
            )
            for item in agent_result.finalized.tasks
        ),
    )

    return ExtractTasksResult(
        outcome=outcome,
        created_task_ids=tuple(agent_result.created_task_ids),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_user_prompt(raw_content: str | ParsedEmail):
    from google.genai import types

    if isinstance(raw_content, ParsedEmail):
        url_text, _failed_urls = _fetch_email_urls(raw_content.raw_urls)
        body_text = f"<content>\n{raw_content.body}{url_text}\n</content>"
        parts: list[types.Part] = [types.Part.from_text(text=body_text)]
        settings = get_settings()
        for filename, data, mime_type in raw_content.attachments:
            if len(data) <= settings.ai_max_attachment_bytes:
                parts.append(types.Part.from_bytes(data=data, mime_type=mime_type))
        return parts
    return f"<content>\n{raw_content}\n</content>"


def _append_memory_context(user_prompt: UserPrompt, memory_context: str) -> UserPrompt:
    if not memory_context:
        return user_prompt

    if isinstance(user_prompt, str):
        return f"{user_prompt}\n\n{memory_context}"

    from google.genai import types

    if not user_prompt:
        return [types.Part.from_text(text=memory_context)]

    patched_parts = list(user_prompt)
    for idx, part in enumerate(patched_parts):
        if part.text:
            patched_parts[idx] = types.Part.from_text(
                text=f"{part.text}\n\n{memory_context}"
            )
            return patched_parts

    patched_parts.insert(0, types.Part.from_text(text=memory_context))
    return patched_parts


def _fetch_email_urls(urls: list[str]) -> tuple[str, list[str]]:
    """Fetch up to settings.ai_url_fetch_cap URLs; return (appended_text, failed_urls)."""
    settings = get_settings()
    fetched_texts: list[str] = []
    failed: list[str] = []

    capped = urls[: settings.ai_url_fetch_cap]
    over_cap = urls[settings.ai_url_fetch_cap :]

    for url in capped:
        try:
            html = fetch_url(url)
            text = strip_html(html)[: settings.ai_url_strip_chars]
            fetched_texts.append(f"\n\n[Content from {url}]\n{text}")
        except Exception:
            failed.append(url)

    failed.extend(over_cap)
    return "".join(fetched_texts), failed


def _derive_source_excerpt(raw_content: str | ParsedEmail) -> str:
    settings = get_settings()
    if isinstance(raw_content, ParsedEmail):
        return raw_content.body[: settings.ai_source_excerpt_chars]
    return str(raw_content)[: settings.ai_source_excerpt_chars]


def _parse_due_date(due_date: str | None) -> date | None:
    if not due_date:
        return None
    try:
        return date.fromisoformat(due_date)
    except ValueError:
        return None
