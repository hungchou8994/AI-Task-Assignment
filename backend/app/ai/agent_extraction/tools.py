"""Extraction tools — the tools available to the extraction agent.

Each tool is decorated with ``@tool`` from the agent framework, which
auto-generates JSON Schema from the type hints and docstring.  The first
``ctx: RunContext[ExtractionDeps]`` parameter is injected by the runner
and hidden from the LLM.

Architecture (current):
  1. Agent calls get_assignee_skills to retrieve available people.
  2. Agent calls create_tasks(source_summary, tasks) — validates with Pydantic,
     persists Source + TaskCandidates to the review queue, commits.
  3. Agent calls recommend_assignees(assignments=[...]) — updates each candidate
     with ranked assignee recommendations, commits.
  4. Agent calls finalize_extraction:
     - persisted mode (no args): builds result from DB after create_tasks, or
     - direct mode (source_summary + tasks): finalizes without persistence dependency.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from app.ai.agent import RunContext, tool
from app.ai.gemini_client import ExtractionResult

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass
class ExtractionDeps:
    """Mutable per-run state injected into tool handlers via RunContext."""

    raw_text: str
    db: Session | None = None
    project_id: str | None = None

    # Persistence context — set by extraction_agent before running
    source_type: str = "text"
    source_excerpt: str = ""
    source_uri: str | None = None
    source_payload: dict = field(default_factory=dict)
    content_hash: str | None = None
    model_version: str | None = None
    prompt_template_hash: str | None = None
    model_latency_ms: int | None = None

    # Marks whether create_tasks was called.
    create_tasks_called: bool = False

    # Marks whether create_tasks completed successfully.
    create_tasks_succeeded: bool = False

    # Accumulates Task IDs actually created after review approval.
    created_task_ids: list[UUID] = field(default_factory=list)

    # Task IDs newly inserted in this run; used for side effects like webhooks.
    new_task_ids: list[UUID] = field(default_factory=list)

    # Accumulates review candidate IDs created or reused by create_tasks.
    created_candidate_ids: list[UUID] = field(default_factory=list)

    # Source summary stored by create_tasks for later result building
    source_summary: str = ""

    # Set by finalize_extraction — holds the built ExtractionResult (or None)
    finalized: ExtractionResult | None = None

    entity_notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Recommendation helpers (used by create_tasks + recommend_assignees)
# ---------------------------------------------------------------------------


def _build_recommendation_payload(recommendation: dict) -> dict:
    rank = int(recommendation.get("rank") or 0)
    confidence_score = float(recommendation.get("confidence_score") or 0.0)
    auto_apply_eligible = bool(recommendation.get("auto_apply_eligible", True))

    if rank == 1:
        default_skills_score = 0.9
        default_reason_code = "best_fit"
    elif rank == 2:
        default_skills_score = 0.75
        default_reason_code = "strong_alternative"
    elif rank == 3:
        default_skills_score = 0.6
        default_reason_code = "backup_candidate"
    else:
        default_skills_score = 0.5
        default_reason_code = "candidate_available"

    workload_score = recommendation.get(
        "workload_score", round(max(0.0, min(1.0, confidence_score)), 4)
    )
    skills_score = recommendation.get("skills_score", default_skills_score)
    historical_fit_score = recommendation.get(
        "historical_fit_score",
        round((max(0.0, min(1.0, confidence_score)) + skills_score) / 2, 4),
    )

    return {
        "rank": rank,
        "person_id": recommendation.get("person_id"),
        "name": recommendation.get("name"),
        "confidence_score": confidence_score,
        "reasoning": recommendation.get("reasoning"),
        "reason_code": recommendation.get("reason_code") or default_reason_code,
        "auto_apply_eligible": auto_apply_eligible,
        "workload_score": workload_score,
        "skills_score": skills_score,
        "historical_fit_score": historical_fit_score,
    }


def _normalize_recommendation_person_ids(db: "Session", recommendations: list[dict]) -> None:
    if not recommendations:
        return

    from sqlalchemy import func

    from app.models import Person

    for recommendation in recommendations:
        raw_person_id = recommendation.get("person_id")
        if raw_person_id:
            try:
                parsed = UUID(str(raw_person_id))
            except (TypeError, ValueError):
                parsed = None
            if parsed and db.get(Person, parsed):
                recommendation["person_id"] = str(parsed)
                continue

        lookup_name = str(recommendation.get("name") or raw_person_id or "").strip()
        if lookup_name:
            person = (
                db.query(Person)
                .filter(func.lower(Person.name) == lookup_name.lower())
                .first()
            )
            if person:
                recommendation["person_id"] = str(person.id)
                continue

        recommendation["person_id"] = None


def _is_auto_apply_allowed(*, task_confidence: float, recommendation: dict) -> bool:
    from app.config import get_settings

    threshold = get_settings().ai_assignee_auto_apply_confidence_threshold
    if task_confidence < threshold:
        return False
    return bool(recommendation.get("auto_apply_eligible", True))


def _resolve_selected_assignee_id(
    db: "Session",
    recommendations: list[dict],
    *,
    task_confidence: float,
) -> UUID | None:
    if not recommendations:
        return None

    first = sorted(recommendations, key=lambda item: item["rank"])[0]
    if not _is_auto_apply_allowed(
        task_confidence=task_confidence, recommendation=first
    ):
        return None

    person_id = first.get("person_id")
    if not person_id:
        return None

    try:
        parsed = UUID(str(person_id))
    except ValueError:
        return None

    from app.models import Person

    return parsed if db.get(Person, parsed) else None


# ---------------------------------------------------------------------------
# Tool 1: get_assignee_skills
# ---------------------------------------------------------------------------


@tool
def get_assignee_skills(ctx: RunContext[ExtractionDeps]) -> str:
    """Lists people in the workspace DB (skills, roles, availability)."""
    if ctx.deps.db is None:
        return json.dumps(
            {
                "available": False,
                "reason": "database session not bound to this extraction run",
                "people": [],
            },
            ensure_ascii=False,
        )
    try:
        from app.models import Person

        rows = ctx.deps.db.query(Person).all()
        people = [
            {
                "id": str(p.id),
                "name": p.name,
                "role": p.role,
                "skills": list(p.skills or []),
                "availability": p.availability.value if p.availability else None,
            }
            for p in rows[:50]
        ]
        return json.dumps(
            {"available": True, "project_id": ctx.deps.project_id, "people": people},
            ensure_ascii=False,
        )
    except Exception as exc:  # noqa: BLE001
        return json.dumps(
            {"available": False, "reason": str(exc), "people": []},
            ensure_ascii=False,
        )


# ---------------------------------------------------------------------------
# Tool 2: create_tasks
# ---------------------------------------------------------------------------


@tool(
    description=(
        "Persist all extracted tasks to the database. All natural-language fields must be in English. "
        "Call exactly once after thinking about all tasks. "
        "Returns a list of {task_candidate_id, task_id, title} to use with recommend_assignees."
    ),
    parameters={
        "type": "object",
        "properties": {
            "source_summary": {
                "type": "string",
                "description": "One-sentence summary of the source content (English).",
            },
            "tasks": {
                "type": "array",
                "description": "Array of extracted tasks (no assignee recommendations here).",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Short, actionable task title (English).",
                        },
                        "description": {
                            "type": "string",
                            "description": "Detailed task description (English).",
                        },
                        "priority": {
                            "type": "string",
                            "enum": ["low", "medium", "high"],
                        },
                        "due_date": {
                            "type": "string",
                            "description": "Due date in ISO-8601 format (YYYY-MM-DD), if known.",
                        },
                        "confidence_score": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                        },
                    },
                    "required": ["title"],
                },
            },
        },
        "required": ["source_summary", "tasks"],
    },
)
def create_tasks(
    ctx: RunContext[ExtractionDeps],
    source_summary: str,
    tasks: list[dict],
) -> str:
    """Persist extracted task candidates to the review queue.

    Args:
        source_summary: One-sentence summary of the source content.
        tasks: Array of task dicts (title, description, priority, due_date, confidence_score).
    """
    ctx.deps.create_tasks_called = True

    db = ctx.deps.db
    if db is None:
        return json.dumps(
            {"ok": False, "error": "no_db_session"},
            ensure_ascii=False,
        )

    project_id_str = ctx.deps.project_id
    if not project_id_str:
        return json.dumps(
            {"ok": False, "error": "no_project_id"},
            ensure_ascii=False,
        )

    # Validate the payload with Pydantic
    try:
        payload = ExtractionResult.model_validate(
            {"source_summary": source_summary, "tasks": tasks}
        )
    except Exception as exc:  # noqa: BLE001
        return json.dumps(
            {"ok": False, "error": f"schema_validation_failed: {exc}"},
            ensure_ascii=False,
        )

    try:
        from app.config import get_settings
        from app.models import (
            CandidateSourceSpan,
            Project,
            Source,
            TaskCandidate,
            TaskCandidateRevision,
            TaskPriority,
        )
        from app.services.candidate_provenance_service import append_candidate_revision

        settings = get_settings()
        project_id = UUID(project_id_str)

        project = db.get(Project, project_id)
        if not project:
            return json.dumps(
                {"ok": False, "error": f"project_not_found: {project_id}"},
                ensure_ascii=False,
            )

        # Find or create Source (idempotency: same content_hash + project + type reuses row)
        content_hash = (
            ctx.deps.content_hash
            or hashlib.sha256(
                ctx.deps.raw_text.encode("utf-8", errors="replace")
            ).hexdigest()
        )

        source = (
            db.query(Source)
            .filter(
                Source.workspace_id == project.workspace_id,
                Source.project_id == project_id,
                Source.source_type == ctx.deps.source_type,
                Source.content_hash == content_hash,
            )
            .first()
        )

        source_uri = (ctx.deps.source_uri or "").strip() or None
        source_payload = dict(ctx.deps.source_payload or {})

        if not source:
            source = Source(
                workspace_id=project.workspace_id,
                project_id=project_id,
                source_type=ctx.deps.source_type,
                uri=source_uri,
                summary=source_summary,
                excerpt=ctx.deps.source_excerpt[: settings.ai_source_excerpt_chars],
                content_hash=content_hash,
                payload=source_payload,
            )
            db.add(source)
            db.flush()
        else:
            source_needs_update = False
            if source_uri and not source.uri:
                source.uri = source_uri
                source_needs_update = True
            if source_payload:
                merged_payload = dict(source.payload or {})
                for key, value in source_payload.items():
                    if value in (None, ""):
                        continue
                    if merged_payload.get(key) in (None, ""):
                        merged_payload[key] = value
                        source_needs_update = True
                if source_needs_update:
                    source.payload = merged_payload
            if source_needs_update:
                db.flush()

            # Idempotency: if review candidates for this source already exist, return them.
            existing_candidates = (
                db.query(TaskCandidate)
                .join(
                    TaskCandidateRevision,
                    TaskCandidateRevision.candidate_id == TaskCandidate.id,
                )
                .join(
                    CandidateSourceSpan,
                    CandidateSourceSpan.candidate_revision_id
                    == TaskCandidateRevision.id,
                )
                .filter(CandidateSourceSpan.source_id == source.id)
                .all()
            )
            if existing_candidates:
                for c in existing_candidates:
                    ctx.deps.created_candidate_ids.append(c.id)
                    if c.approved_task_id:
                        ctx.deps.created_task_ids.append(c.approved_task_id)
                created = [
                    {
                        "task_candidate_id": str(c.id),
                        "task_id": str(c.approved_task_id) if c.approved_task_id else None,
                        "title": c.title,
                    }
                    for c in existing_candidates
                ]
                ctx.deps.source_summary = source_summary
                ctx.deps.create_tasks_succeeded = True
                return json.dumps(
                    {"ok": True, "idempotent": True, "created": created},
                    ensure_ascii=False,
                )

        created: list[dict] = []
        for item in payload.tasks:
            due_date: date | None = None
            if item.due_date:
                try:
                    due_date = date.fromisoformat(item.due_date)
                except ValueError:
                    pass

            confidence = max(0.0, min(1.0, item.confidence_score))
            candidate = TaskCandidate(
                project_id=project_id,
                title=item.title[: settings.ai_task_title_max_chars],
                description=item.description,
                priority=TaskPriority(item.priority),
                due_date=due_date,
                selected_assignee_id=None,
                confidence_score=confidence,
                source_type=ctx.deps.source_type,
                source_excerpt=ctx.deps.source_excerpt[
                    : settings.ai_source_excerpt_chars
                ],
                source_summary=source_summary,
                assignee_recommendations=[],
            )
            db.add(candidate)
            db.flush()

            append_candidate_revision(
                db,
                candidate,
                revision_type="extracted",
                source_id=source.id,
                model_version=ctx.deps.model_version,
                prompt_template_hash=ctx.deps.prompt_template_hash,
                model_latency_ms=ctx.deps.model_latency_ms,
                event_metadata={"flow": "extraction_pipeline"},
            )

            ctx.deps.created_candidate_ids.append(candidate.id)
            created.append(
                {
                    "task_candidate_id": str(candidate.id),
                    "task_id": None,
                    "title": item.title,
                }
            )

        db.commit()

        # Store source summary for later result building (after agent loop ends)
        ctx.deps.source_summary = source_summary
        ctx.deps.create_tasks_succeeded = True

        return json.dumps(
            {
                "ok": True,
                "created": created,
                "message": (
                    "Task candidates persisted for review. Now call recommend_assignees with the "
                    "task_candidate_ids above, then finalize_extraction."
                ),
            },
            ensure_ascii=False,
        )

    except Exception as exc:  # noqa: BLE001
        db.rollback()
        return json.dumps(
            {"ok": False, "error": f"db_error: {exc}"},
            ensure_ascii=False,
        )


# ---------------------------------------------------------------------------
# Tool 3: recommend_assignees
# ---------------------------------------------------------------------------


@tool(
    description=(
        "Attach ranked assignee recommendations to previously created tasks. "
        "Call after create_tasks with the task_candidate_ids it returned."
    ),
    parameters={
        "type": "object",
        "properties": {
            "assignments": {
                "type": "array",
                "description": "One entry per task.",
                "items": {
                    "type": "object",
                    "properties": {
                        "task_candidate_id": {
                            "type": "string",
                            "description": "UUID from create_tasks response.",
                        },
                        "recommendations": {
                            "type": "array",
                            "description": "Ranked list of 1-3 assignee recommendations.",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "rank": {
                                        "type": "integer",
                                        "minimum": 1,
                                        "maximum": 3,
                                    },
                                    "person_id": {"type": "string"},
                                    "name": {"type": "string"},
                                    "confidence_score": {
                                        "type": "number",
                                        "minimum": 0.0,
                                        "maximum": 1.0,
                                    },
                                    "reasoning": {"type": "string"},
                                },
                                "required": [
                                    "rank",
                                    "person_id",
                                    "name",
                                    "confidence_score",
                                    "reasoning",
                                ],
                            },
                            "maxItems": 3,
                        },
                    },
                    "required": ["task_candidate_id", "recommendations"],
                },
            }
        },
        "required": ["assignments"],
    },
)
def recommend_assignees(
    ctx: RunContext[ExtractionDeps],
    assignments: list[dict],
) -> str:
    """Attach assignee recommendations to task candidates.

    Args:
        assignments: List of {task_candidate_id, recommendations} dicts.
    """
    db = ctx.deps.db
    if db is None:
        return json.dumps({"ok": False, "error": "no_db_session"}, ensure_ascii=False)

    try:
        from app.models import Task, TaskCandidate

        updated = 0
        for assignment in assignments:
            raw_id = assignment.get("task_candidate_id")
            recs_raw = assignment.get("recommendations") or []

            try:
                candidate_id = UUID(str(raw_id))
            except (TypeError, ValueError):
                continue

            candidate = db.get(TaskCandidate, candidate_id)
            if not candidate:
                continue

            payloads = [_build_recommendation_payload(r) for r in recs_raw]
            _normalize_recommendation_person_ids(db, payloads)
            selected_assignee_id = _resolve_selected_assignee_id(
                db,
                payloads,
                task_confidence=float(candidate.confidence_score),
            )

            candidate.assignee_recommendations = payloads
            candidate.selected_assignee_id = selected_assignee_id

            if candidate.approved_task_id:
                task = db.get(Task, candidate.approved_task_id)
                if task:
                    task.assignee_id = selected_assignee_id

            updated += 1

        db.commit()

        return json.dumps(
            {"ok": True, "updated": updated},
            ensure_ascii=False,
        )

    except Exception as exc:  # noqa: BLE001
        db.rollback()
        return json.dumps(
            {"ok": False, "error": f"db_error: {exc}"},
            ensure_ascii=False,
        )


# ---------------------------------------------------------------------------
# Tool 4: finalize_extraction
# ---------------------------------------------------------------------------


@tool(
    description=(
        "Call this tool exactly once when the extraction workflow is complete. "
        "You can either (1) finalize persisted DB state after create_tasks, or "
        "(2) pass source_summary/tasks directly to finalize without persistence."
    ),
    parameters={
        "type": "object",
        "properties": {
            "source_summary": {
                "type": "string",
                "description": "Optional direct-finalize source summary.",
            },
            "tasks": {
                "type": "array",
                "description": (
                    "Optional direct-finalize tasks. If provided, source_summary must also be provided."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "priority": {
                            "type": "string",
                            "enum": ["low", "medium", "high"],
                        },
                        "due_date": {"type": "string"},
                        "confidence_score": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                        },
                        "assignee_recommendations": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "rank": {
                                        "type": "integer",
                                        "minimum": 1,
                                        "maximum": 3,
                                    },
                                    "person_id": {"type": "string"},
                                    "name": {"type": "string"},
                                    "confidence_score": {
                                        "type": "number",
                                        "minimum": 0.0,
                                        "maximum": 1.0,
                                    },
                                    "reasoning": {"type": "string"},
                                },
                                "required": [
                                    "rank",
                                    "name",
                                    "confidence_score",
                                    "reasoning",
                                ],
                            },
                        },
                    },
                    "required": ["title", "priority"],
                },
            },
        },
        "required": [],
    },
)
def finalize_extraction(
    ctx: RunContext[ExtractionDeps],
    source_summary: str | None = None,
    tasks: list[dict] | None = None,
) -> str:
    """Build the final ExtractionResult from DB and signal completion.

    The runner detects deps.finalized (truthy) and exits the loop immediately.
    """
    db = ctx.deps.db

    # Persisted DB state is the source of truth after create_tasks succeeds.
    # Some model calls provide source_summary again during finalization; that
    # must not switch the result into direct mode with an empty tasks list.
    if ctx.deps.create_tasks_succeeded:
        if source_summary is not None:
            ctx.deps.source_summary = source_summary
    # Mode A: direct result mode (no persistence dependency).
    elif source_summary is not None or tasks is not None:
        if source_summary is None:
            return json.dumps(
                {
                    "ok": False,
                    "error": "source_summary is required when tasks are provided",
                },
                ensure_ascii=False,
            )
        try:
            direct_payload = ExtractionResult.model_validate(
                {
                    "source_summary": source_summary,
                    "tasks": tasks or [],
                }
            )
        except Exception as exc:  # noqa: BLE001
            return json.dumps(
                {"ok": False, "error": f"schema_validation_failed: {exc}"},
                ensure_ascii=False,
            )

        ctx.deps.finalized = direct_payload
        return json.dumps(
            {
                "ok": True,
                "mode": "direct",
                "tasks_finalized": len(direct_payload.tasks),
            },
            ensure_ascii=False,
        )

    # Mode B: persisted DB mode.
    if not ctx.deps.create_tasks_succeeded:
        return json.dumps(
            {
                "ok": False,
                "error": (
                    "no extraction result available — call create_tasks first "
                    "or pass source_summary/tasks directly"
                ),
            },
            ensure_ascii=False,
        )

    from app.ai.gemini_client import ExtractedTask
    from app.models import TaskCandidate

    tasks_result: list[ExtractedTask] = []
    candidate_ids = list(ctx.deps.created_candidate_ids)
    if not candidate_ids and ctx.deps.created_task_ids and db:
        candidate_ids = [
            candidate.id
            for candidate in db.query(TaskCandidate)
            .filter(TaskCandidate.approved_task_id.in_(ctx.deps.created_task_ids))
            .all()
        ]

    for candidate_id in candidate_ids:
        candidate = db.get(TaskCandidate, candidate_id) if db else None
        if candidate:
            tasks_result.append(
                ExtractedTask(
                    title=candidate.title,
                    description=candidate.description,
                    priority=candidate.priority.value,
                    due_date=str(candidate.due_date) if candidate.due_date else None,
                    confidence_score=candidate.confidence_score,
                    assignee_recommendations=candidate.assignee_recommendations or [],
                )
            )

    ctx.deps.finalized = ExtractionResult(
        source_summary=ctx.deps.source_summary,
        tasks=tasks_result,
    )

    return json.dumps(
        {"ok": True, "mode": "persisted", "tasks_finalized": len(tasks_result)},
        ensure_ascii=False,
    )


# ---------------------------------------------------------------------------
# All tools in registration order
# ---------------------------------------------------------------------------

ALL_EXTRACTION_TOOLS = [
    get_assignee_skills,
    create_tasks,
    recommend_assignees,
    finalize_extraction,
]
