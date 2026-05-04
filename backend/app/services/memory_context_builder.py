from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Project, Workspace
from app.schemas import ExtractTasksCommand
from app.services.memory_policy import MemoryClass, MemoryScope, resolve_policy
from app.services.memory_service import MemoryHit, MemoryService


@dataclass(frozen=True)
class MemoryContextBuildResult:
    context: str
    scope: MemoryScope | None
    query: str
    result_count: int
    latency_ms: int


def build_extraction_memory_context(db: Session, command: ExtractTasksCommand) -> str:
    result = build_extraction_memory_bundle(db, command)
    return result.context


def build_extraction_memory_bundle(
    db: Session,
    command: ExtractTasksCommand,
) -> MemoryContextBuildResult:
    settings = get_settings()
    if not settings.memory_enabled:
        return MemoryContextBuildResult(
            context="",
            scope=None,
            query="",
            result_count=0,
            latency_ms=0,
        )

    scope = _resolve_scope_from_project(db, project_id=command.project_id)
    decision = resolve_policy(action="extraction", scope=scope, role="system")
    memory_service = MemoryService()

    query = _compose_query(command.content)
    classes = [item.value for item in decision.allowed_classes]
    k = settings.memory_default_results
    project_result = memory_service.search(
        query=query, scope=scope, classes=classes, k=k
    )
    merged_hits = list(project_result.hits)

    min_project_hits = 2
    if (
        decision.allow_scope_widening
        and scope.project_id is not None
        and len(project_result.hits) < min_project_hits
    ):
        widened_scope = MemoryScope(
            org_id=scope.org_id,
            workspace_id=scope.workspace_id,
            project_id=None,
        )
        widened_result = memory_service.search(
            query=query,
            scope=widened_scope,
            classes=classes,
            k=k,
        )
        merged_hits = _merge_hits(merged_hits, widened_result.hits)

    ranked_hits = _rank_hits(merged_hits, allowed_classes=decision.allowed_classes)
    return MemoryContextBuildResult(
        context=_format_context(
            ranked_hits, max_chars=settings.memory_max_context_chars
        ),
        scope=scope,
        query=query,
        result_count=len(ranked_hits),
        latency_ms=getattr(project_result, "latency_ms", 0),
    )


def build_recommendation_memory_context(
    db: Session,
    project_id: str,
    task_title: str,
    task_description: str,
) -> str:
    settings = get_settings()
    if not settings.memory_enabled:
        return ""

    scope = _resolve_scope_from_project(db, project_id=project_id)
    decision = resolve_policy(action="recommendation", scope=scope, role="system")
    memory_service = MemoryService()

    query = _compose_query(f"{task_title}\n{task_description}")
    classes = [item.value for item in decision.allowed_classes]
    hits = memory_service.search(
        query=query,
        scope=scope,
        classes=classes,
        k=settings.memory_default_results,
    ).hits

    ranked_hits = _rank_hits(list(hits), allowed_classes=decision.allowed_classes)
    return _format_context(ranked_hits, max_chars=settings.memory_max_context_chars)


def _resolve_scope_from_project(db: Session, project_id: str) -> MemoryScope:
    try:
        project_uuid = UUID(project_id)
    except ValueError as exc:
        raise ValueError(f"invalid project id for memory scope: {project_id}") from exc

    row = (
        db.query(Project.id, Workspace.id, Workspace.org_id)
        .join(Workspace, Workspace.id == Project.workspace_id)
        .filter(Project.id == project_uuid)
        .one_or_none()
    )
    if row is None:
        raise ValueError(f"project not found for memory scope: {project_id}")

    return MemoryScope(
        org_id=str(row[2]),
        workspace_id=str(row[1]),
        project_id=str(row[0]),
    )


def _compose_query(content: str, *, max_chars: int = 500) -> str:
    return " ".join(content.split())[:max_chars]


def _merge_hits(
    current_hits: list[MemoryHit], extra_hits: tuple[MemoryHit, ...]
) -> list[MemoryHit]:
    seen = {
        (hit.class_name, hit.fact, hit.project_id, hit.timestamp)
        for hit in current_hits
    }
    merged = list(current_hits)
    for hit in extra_hits:
        key = (hit.class_name, hit.fact, hit.project_id, hit.timestamp)
        if key in seen:
            continue
        merged.append(hit)
        seen.add(key)
    return merged


def _rank_hits(
    hits: list[MemoryHit],
    *,
    allowed_classes: tuple[MemoryClass, ...],
) -> list[MemoryHit]:
    if not hits:
        return []

    class_order = {
        class_name.value: idx for idx, class_name in enumerate(allowed_classes)
    }

    def _sort_key(hit: MemoryHit) -> tuple[int, float, float, str]:
        relevance_rank = class_order.get(hit.class_name, len(class_order) + 1)
        recency = _timestamp_to_epoch(hit.timestamp)
        return (relevance_rank, -hit.confidence_score, -recency, hit.fact)

    sorted_hits = sorted(hits, key=_sort_key)

    capped_per_class = 2
    included_per_class: dict[str, int] = {}
    selected: list[MemoryHit] = []
    for hit in sorted_hits:
        count = included_per_class.get(hit.class_name, 0)
        if count >= capped_per_class:
            continue
        selected.append(hit)
        included_per_class[hit.class_name] = count + 1
    return selected


def _format_context(hits: list[MemoryHit], *, max_chars: int) -> str:
    if not hits or max_chars <= 0:
        return ""

    header = "## MEMORY CONTEXT"
    lines: list[str] = []
    total_chars = len(header)

    for hit in hits:
        project_value = hit.project_id or "unknown"
        ts_value = hit.timestamp or "unknown"
        fact = " ".join(hit.fact.split())
        line = (
            f"- [class={hit.class_name}][project={project_value}][ts={ts_value}] {fact}"
        )
        projected_total = total_chars + 1 + len(line)
        if projected_total > max_chars:
            continue
        lines.append(line)
        total_chars = projected_total

    if not lines:
        return ""
    return header + "\n" + "\n".join(lines)


def _timestamp_to_epoch(timestamp: str | None) -> float:
    if not timestamp:
        return 0.0
    normalized = timestamp.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(normalized).timestamp()
    except ValueError:
        return 0.0
