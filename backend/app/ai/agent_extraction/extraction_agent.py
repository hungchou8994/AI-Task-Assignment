"""Public entrypoints for advanced extraction modes.

`app.ai.agent_extraction` (think → act → observe), built on the
`app.ai.agent` framework (Agent + Runner + @tool).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

from google.genai import types

from app.ai.agent import Agent, JobEventEmitter, NullEmitter, Runner
from app.ai.agent.models import GeminiModel, OpenAIModel
from app.ai.agent_extraction.tools import ALL_EXTRACTION_TOOLS, ExtractionDeps
from app.ai.gemini_client import ExtractionResult
from app.config import get_settings

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

UserPrompt = str | list[types.Part]

# Skills directory (relative to this file)
_SKILLS_DIR = Path(__file__).parent / "skills"

AGENT_INTRO_JA: str = (
    "[Extraction Agent] Extract actionable tasks from the source content. "
    "Call tools autonomously as needed and decide next steps based on observations. "
    "If persisting, call create_tasks exactly once, then recommend_assignees if applicable, "
    "and finally call finalize_extraction to end the workflow."
)


@dataclass
class AgentRunResult:
    """Return value of extraction runner entrypoints."""

    finalized: ExtractionResult
    created_task_ids: list[UUID] = field(default_factory=list)
    new_task_ids: list[UUID] = field(default_factory=list)


def _flatten_raw_text(user_prompt: UserPrompt) -> str:
    """Convert a UserPrompt into a flat string for tool context."""
    if isinstance(user_prompt, str):
        return user_prompt
    chunks: list[str] = []
    for p in user_prompt:
        if p.text:
            chunks.append(p.text)
        else:
            chunks.append("[binary attachment present]")
    return "\n".join(chunks)


def _has_binary_parts(user_prompt: UserPrompt) -> bool:
    """Return True if user_prompt contains any non-text (binary) Part."""
    if isinstance(user_prompt, str):
        return False
    return any(not p.text for p in user_prompt)


def _build_extraction_agent() -> Agent:
    """Create the extraction agent config."""
    settings = get_settings()
    provider = settings.ai_agent_provider

    def _model_factory() -> GeminiModel | OpenAIModel:
        if provider == "openai":
            return OpenAIModel(
                api_key=settings.openai_api_key,
                model=settings.openai_model,
                base_url=settings.openai_base_url or None,
            )

        use_vertexai = settings.gemini_vertexai or settings.google_genai_use_vertexai
        if use_vertexai:
            if settings.gemini_vertex_use_api_key:
                if not settings.gemini_api_key:
                    raise ValueError("GEMINI_API_KEY not configured")
                return GeminiModel(
                    api_key=settings.gemini_api_key,
                    model=settings.gemini_model,
                    vertexai=True,
                )

            project = settings.gemini_vertex_project or settings.google_cloud_project
            location = (
                settings.gemini_vertex_location
                or settings.google_cloud_location
                or "us-central1"
            )
            if not project:
                raise ValueError(
                    "Vertex AI Gemini requires GEMINI_VERTEX_PROJECT or GOOGLE_CLOUD_PROJECT"
                )
            return GeminiModel(
                model=settings.gemini_model,
                vertexai=True,
                project=project,
                location=location,
            )

        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY not configured")
        return GeminiModel(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
        )

    temperature = (
        settings.openai_temperature
        if provider == "openai"
        else settings.gemini_temperature
    )

    return Agent(
        name="extraction",
        instructions="",  # overridden below
        skills=["extraction_policy", "assignee_policy"],
        skills_dir=_SKILLS_DIR,
        tools=ALL_EXTRACTION_TOOLS,
        model=_model_factory,
        max_iterations=20,
        max_context_turns=28,
        empty_rounds_cap=3,
        temperature=temperature,
        max_tokens=8192,
        mutating_tools={"create_tasks", "recommend_assignees"},
    )


def _prepare_extraction_run(
    user_prompt: UserPrompt,
    extraction_system_prompt: str,
    *,
    db: "Session | None" = None,
    project_id: "str | None" = None,
    job_id: "str | None" = None,
    source_type: str = "text",
    source_excerpt: str = "",
    source_uri: str | None = None,
    source_payload: dict | None = None,
    content_hash: str | None = None,
    model_version: str | None = None,
    prompt_template_hash: str | None = None,
) -> tuple[Agent, str, ExtractionDeps, JobEventEmitter | NullEmitter]:
    """Prepare shared runner inputs for async/sync entrypoints."""
    raw_text = _flatten_raw_text(user_prompt)
    deps = ExtractionDeps(
        raw_text=raw_text,
        db=db,
        project_id=project_id,
        source_type=source_type,
        source_excerpt=source_excerpt,
        source_uri=source_uri,
        source_payload=dict(source_payload or {}),
        content_hash=content_hash,
        model_version=model_version,
        prompt_template_hash=prompt_template_hash,
    )

    agent = _build_extraction_agent()
    agent.instructions = extraction_system_prompt

    emitter: JobEventEmitter | NullEmitter = (
        JobEventEmitter(job_id) if job_id else NullEmitter()
    )

    if isinstance(user_prompt, str):
        prompt_text = AGENT_INTRO_JA + "\n\n" + user_prompt
    else:
        prompt_text = AGENT_INTRO_JA + "\n\n" + raw_text

    return agent, prompt_text, deps, emitter


async def run_autonomous_extraction_async(
    user_prompt: UserPrompt,
    extraction_system_prompt: str,
    *,
    db: "Session | None" = None,
    project_id: "str | None" = None,
    job_id: "str | None" = None,
    source_type: str = "text",
    source_excerpt: str = "",
    source_uri: str | None = None,
    source_payload: dict | None = None,
    content_hash: str | None = None,
    model_version: str | None = None,
    prompt_template_hash: str | None = None,
) -> AgentRunResult:
    """Run the autonomous agent extraction loop asynchronously.

    The agent calls create_tasks (which persists candidates to DB),
    recommend_assignees (which attaches assignee recommendations),
    and finalize_extraction (which builds the ExtractionResult from DB).

    Returns AgentRunResult with the finalized extraction and created task IDs.
    Raises RuntimeError if the loop ends without finalize_extraction being called.
    """
    agent, prompt_text, deps, emitter = _prepare_extraction_run(
        user_prompt,
        extraction_system_prompt,
        db=db,
        project_id=project_id,
        job_id=job_id,
        source_type=source_type,
        source_excerpt=source_excerpt,
        source_uri=source_uri,
        source_payload=source_payload,
        content_hash=content_hash,
        model_version=model_version,
        prompt_template_hash=prompt_template_hash,
    )

    result = await Runner.run(
        agent,
        prompt_text,
        deps=deps,
        emitter=emitter,
    )

    # The agent signals completion via finalize_extraction, which builds
    # the ExtractionResult from DB ground truth and stores it in deps.finalized.
    if not deps.finalized:
        error_detail = ""
        final_response = getattr(result, "final_response", None)
        if final_response and final_response.content.strip():
            error_detail = f" Last model error: {final_response.content.strip()}"
        raise RuntimeError(
            "[ExtractionAgent] agent loop ended without calling finalize_extraction. "
            f"Check the agent logs for details.{error_detail}"
        )

    logger.info(
        "[ExtractionAgent] completed in %d iterations, tasks=%d",
        result.iterations,
        len(deps.finalized.tasks),
    )
    return AgentRunResult(
        finalized=deps.finalized,
        created_task_ids=list(deps.created_task_ids),
        new_task_ids=list(deps.new_task_ids),
    )


def run_autonomous_extraction_sync(
    user_prompt: UserPrompt,
    extraction_system_prompt: str,
    *,
    db: "Session | None" = None,
    project_id: "str | None" = None,
    job_id: "str | None" = None,
    source_type: str = "text",
    source_excerpt: str = "",
    source_uri: str | None = None,
    source_payload: dict | None = None,
    content_hash: str | None = None,
    model_version: str | None = None,
    prompt_template_hash: str | None = None,
) -> AgentRunResult:
    """Sync compatibility wrapper around async extraction entrypoint."""
    agent, prompt_text, deps, emitter = _prepare_extraction_run(
        user_prompt,
        extraction_system_prompt,
        db=db,
        project_id=project_id,
        job_id=job_id,
        source_type=source_type,
        source_excerpt=source_excerpt,
        source_uri=source_uri,
        source_payload=source_payload,
        content_hash=content_hash,
        model_version=model_version,
        prompt_template_hash=prompt_template_hash,
    )

    result = Runner.run_sync(
        agent,
        prompt_text,
        deps=deps,
        emitter=emitter,
    )

    if not deps.finalized:
        error_detail = ""
        final_response = getattr(result, "final_response", None)
        if final_response and final_response.content.strip():
            error_detail = f" Last model error: {final_response.content.strip()}"
        raise RuntimeError(
            "[ExtractionAgent] agent loop ended without calling finalize_extraction. "
            f"Check the agent logs for details.{error_detail}"
        )

    logger.info(
        "[ExtractionAgent] completed in %d iterations, tasks=%d",
        result.iterations,
        len(deps.finalized.tasks),
    )
    return AgentRunResult(
        finalized=deps.finalized,
        created_task_ids=list(deps.created_task_ids),
        new_task_ids=list(deps.new_task_ids),
    )
