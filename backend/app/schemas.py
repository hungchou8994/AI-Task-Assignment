from datetime import date, datetime
from uuid import UUID
from typing import Optional, List, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.dataclasses import dataclass as pydantic_dataclass
from app.models import (
    TaskStatus,
    TaskPriority,
    AvailabilityStatus,
    CandidateStatus,
    CandidateApprovalAction,
    TaskActivityAction,
    TaskDependencyType,
)


class _BaseResponse(BaseModel):
    """Base for all response models — enables ORM mode automatically."""
    model_config = ConfigDict(from_attributes=True)


# ─── AI Extraction Domain Objects ──────────────────────────────────────────────
# These were previously in app.domain.entities.ai_extraction. They are plain
# frozen dataclasses describing extraction inputs/outputs — no framework deps.


@pydantic_dataclass(frozen=True)
class ExtractTasksCommand:
    source_type: Literal["text", "url", "email"]
    content: str
    project_id: str
    job_id: str | None = None


@pydantic_dataclass(frozen=True)
class AssigneeRecommendationItem:
    rank: int
    person_id: Optional[str]
    name: str
    confidence_score: float
    reasoning: str
    reason_code: Optional[str] = None
    auto_apply_eligible: Optional[bool] = None
    workload_score: Optional[float] = None
    skills_score: Optional[float] = None
    historical_fit_score: Optional[float] = None


@pydantic_dataclass(frozen=True)
class ExtractedTaskItem:
    title: str
    description: Optional[str]
    priority: Literal["low", "medium", "high"]
    confidence_score: float
    due_date: Optional[date] = Field(
        default_factory=date.today,
        description="Due date for the task. Defaults to today when omitted.",
    )
    assignee_recommendations: tuple[AssigneeRecommendationItem, ...] = ()


@pydantic_dataclass(frozen=True)
class ExtractionOutcome:
    source_summary: str
    tasks: tuple[ExtractedTaskItem, ...]


@pydantic_dataclass(frozen=True)
class ExtractionServiceResult:
    outcome: ExtractionOutcome
    source_excerpt: str
    model_version: str | None = None
    prompt_template_hash: str | None = None
    model_latency_ms: int | None = None


@pydantic_dataclass(frozen=True)
class ExtractTasksResult:
    """Carries the extraction outcome and any Task IDs created during persistence.

    In review-queue mode, AI extraction creates candidates first, so this is
    normally empty until candidates are approved into real tasks.
    """

    outcome: ExtractionOutcome
    created_task_ids: tuple[UUID, ...]

    @property
    def tasks(self) -> tuple[ExtractedTaskItem, ...]:
        return self.outcome.tasks

    @property
    def source_summary(self) -> str:
        return self.outcome.source_summary


# ─── Auth Schemas ──────────────────────────────────────────────────────────────


class UserRegister(BaseModel):
    email: str
    password: str = Field(min_length=8)


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(_BaseResponse):
    id: UUID
    email: str
    created_at: datetime


# ─── Organization Schemas ──────────────────────────────────────────────────────


class OrganizationResponse(_BaseResponse):
    id: UUID
    name: str
    slug: str
    settings: dict
    created_at: datetime


class OrgMembershipResponse(_BaseResponse):
    org_id: UUID
    user_id: UUID
    role: str
    created_at: datetime


# ─── Workspace Schemas ─────────────────────────────────────────────────────────


class WorkspaceCreate(BaseModel):
    name: str
    description: Optional[str] = None
    org_id: Optional[UUID] = None


class WorkspaceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class WorkspaceResponse(_BaseResponse):
    id: UUID
    name: str
    description: Optional[str]
    org_id: UUID
    owner_id: UUID
    created_at: datetime
    updated_at: datetime


class WorkspaceMembershipResponse(_BaseResponse):
    workspace_id: UUID
    user_id: UUID
    role: str
    created_at: datetime


# ─── Service Identity Schemas ──────────────────────────────────────────────────


class ServiceIdentityResponse(_BaseResponse):
    id: UUID
    org_id: UUID
    name: str
    kind: str
    created_at: datetime


# ─── Feature Entitlement Schemas ────────────────────────────────────────────────


class FeatureEntitlementResponse(_BaseResponse):
    org_id: UUID
    feature_key: str
    enabled: bool
    created_at: datetime


# ─── Project Schemas ───────────────────────────────────────────────────────────


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class ProjectResponse(_BaseResponse):
    id: UUID
    name: str
    description: Optional[str]
    workspace_id: UUID
    created_at: datetime
    updated_at: datetime


# ─── Task Schemas ──────────────────────────────────────────────────────────────


class TaskCreate(BaseModel):
    title: str
    project_id: UUID
    description: Optional[str] = None
    status: TaskStatus = TaskStatus.todo
    priority: TaskPriority = TaskPriority.medium
    due_date: Optional[date] = None
    assignee_id: Optional[UUID] = None
    needs_review: bool = False


class TaskUpdate(BaseModel):
    """PUT — any combination of fields; only sent fields are updated."""

    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    due_date: Optional[date] = None
    assignee_id: Optional[UUID] = None


class TaskPatch(BaseModel):
    """PATCH — assignee, labels (replace set), and/or estimate snapshot."""

    assignee_id: Optional[UUID] = None
    label_ids: Optional[List[UUID]] = None
    estimated_hours: Optional[float] = None
    actual_hours: Optional[float] = None


class TaskResponse(_BaseResponse):
    id: UUID
    title: str
    description: Optional[str]
    status: TaskStatus
    priority: TaskPriority
    due_date: Optional[date]
    assignee_id: Optional[UUID]
    project_id: UUID
    needs_review: bool
    created_at: datetime
    updated_at: datetime
    archived_at: Optional[datetime] = None
    label_ids: List[UUID] = Field(default_factory=list)
    estimated_hours: Optional[float] = None
    actual_hours: Optional[float] = None


class TaskStatusHistoryEntry(_BaseResponse):

    id: UUID
    task_id: UUID
    from_status: Optional[str]
    to_status: str
    changed_at: datetime
    changed_by_actor_type: str
    changed_by_actor_id: Optional[UUID]


class TaskDependencyCreate(BaseModel):
    blocks_task_id: UUID
    dependency_type: TaskDependencyType = TaskDependencyType.blocks


class TaskDependencyResponse(_BaseResponse):

    id: UUID
    dependent_task_id: UUID
    blocks_task_id: UUID
    dependency_type: TaskDependencyType


class LabelCreate(BaseModel):
    name: str
    color: Optional[str] = None


class LabelResponse(_BaseResponse):

    id: UUID
    workspace_id: UUID
    name: str
    color: Optional[str]
    created_at: datetime


class TaskActivityEventResponse(_BaseResponse):

    id: UUID
    task_id: UUID
    project_id: UUID
    action_type: TaskActivityAction
    field_name: Optional[str]
    before_value: Optional[object]
    after_value: Optional[object]
    event_metadata: dict
    actor_type: str
    actor_label: Optional[str]
    actor_id: Optional[UUID]
    occurred_at: datetime
    created_at: datetime


# ─── Task Comments ─────────────────────────────────────────────────────────────

class TaskCommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=10000)

    @field_validator("body", mode="before")
    @classmethod
    def strip_and_reject_whitespace(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("body must not be empty or whitespace-only")
        return stripped


class TaskCommentUpdate(BaseModel):
    body: str = Field(min_length=1, max_length=10000)

    @field_validator("body", mode="before")
    @classmethod
    def strip_and_reject_whitespace(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("body must not be empty or whitespace-only")
        return stripped


class TaskCommentResponse(_BaseResponse):
    id: UUID
    task_id: UUID
    author_id: Optional[UUID]
    author_email: str
    body: str
    is_edited: bool
    created_at: datetime
    edited_at: Optional[datetime]

    @model_validator(mode="after")
    def compute_is_edited(self) -> "TaskCommentResponse":
        object.__setattr__(self, "is_edited", self.edited_at is not None)
        return self


class PersonCreate(BaseModel):
    name: str
    email: Optional[str] = None
    role: Optional[str] = None
    skills: Optional[List[str]] = None
    bio: Optional[str] = None
    availability: Optional[AvailabilityStatus] = None


class PersonUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    skills: Optional[List[str]] = None
    bio: Optional[str] = None
    availability: Optional[AvailabilityStatus] = None


class PersonResponse(_BaseResponse):
    id: UUID
    name: str
    email: Optional[str]
    role: Optional[str]
    skills: Optional[List[str]]
    bio: Optional[str]
    availability: Optional[AvailabilityStatus]
    created_at: datetime


class AssigneeRecommendation(BaseModel):
    rank: int = Field(ge=1, le=3)
    person_id: Optional[UUID] = None
    name: str
    confidence_score: float = Field(ge=0, le=1)
    reasoning: str
    reason_code: Optional[str] = None
    auto_apply_eligible: Optional[bool] = None
    workload_score: Optional[float] = Field(default=None, ge=0, le=1)
    skills_score: Optional[float] = Field(default=None, ge=0, le=1)
    historical_fit_score: Optional[float] = Field(default=None, ge=0, le=1)


class TaskAssigneeRecommendationsResponse(BaseModel):
    recommendations: List[AssigneeRecommendation] = Field(default_factory=list)


class TaskCandidateResponse(_BaseResponse):

    id: UUID
    project_id: UUID
    title: str
    description: Optional[str]
    priority: TaskPriority
    due_date: Optional[date]
    selected_assignee_id: Optional[UUID]
    confidence_score: float = Field(ge=0, le=1)
    source_type: str
    source_excerpt: Optional[str]
    source_summary: str
    assignee_recommendations: List[AssigneeRecommendation] = Field(
        default_factory=list,
        max_length=3,
    )
    status: CandidateStatus
    approved_task_id: Optional[UUID]
    approved_at: Optional[datetime]
    rejected_at: Optional[datetime]
    undo_expires_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class SourceResponse(_BaseResponse):

    id: UUID
    workspace_id: UUID
    project_id: Optional[UUID]
    source_type: str
    title: Optional[str]
    uri: Optional[str]
    content_hash: Optional[str]
    summary: Optional[str]
    excerpt: Optional[str]
    payload: dict
    created_by_user_id: Optional[UUID]
    created_at: datetime


class TaskSourceLinkResponse(_BaseResponse):

    task_id: UUID
    source_id: UUID
    link_type: str
    confidence_score: Optional[float]
    created_at: datetime
    source: Optional[SourceResponse] = None


class BulkDeleteTasksRequest(BaseModel):
    task_ids: List[UUID] = Field(min_length=1, max_length=500)


class BulkDeleteTasksResponse(BaseModel):
    deleted_count: int


class CandidateSourceSpanResponse(_BaseResponse):

    id: UUID
    candidate_revision_id: UUID
    source_id: UUID
    span_start: Optional[int]
    span_end: Optional[int]
    snippet: Optional[str]
    created_at: datetime


class TaskCandidateRevisionResponse(_BaseResponse):

    id: UUID
    candidate_id: UUID
    revision_number: int
    revision_type: str
    title: str
    description: Optional[str]
    priority: TaskPriority
    due_date: Optional[date]
    selected_assignee_id: Optional[UUID]
    confidence_score: float
    source_type: str
    source_excerpt: Optional[str]
    source_summary: str
    model_version: Optional[str]
    prompt_template_hash: Optional[str]
    model_latency_ms: Optional[int]
    event_metadata: dict
    created_at: datetime
    source_spans: List[CandidateSourceSpanResponse] = Field(default_factory=list)


class CandidateApprovalEventResponse(_BaseResponse):

    id: UUID
    candidate_id: UUID
    task_id: Optional[UUID]
    action: CandidateApprovalAction
    actor_type: str
    actor_id: Optional[UUID]
    event_metadata: dict
    created_at: datetime


class CandidateProvenanceTimelineEvent(BaseModel):
    event_type: str
    event_id: str
    candidate_id: UUID
    occurred_at: datetime
    data: dict


class CandidateProvenanceResponse(BaseModel):
    candidate_id: UUID
    approved_task_id: Optional[UUID]
    candidate_status: CandidateStatus
    revisions: List[TaskCandidateRevisionResponse] = Field(default_factory=list)
    approval_events: List[CandidateApprovalEventResponse] = Field(default_factory=list)
    timeline: List[CandidateProvenanceTimelineEvent] = Field(default_factory=list)


class TaskCandidatePatch(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[TaskPriority] = None
    due_date: Optional[date] = None
    selected_assignee_id: Optional[UUID] = None


class ApproveCandidateResponse(BaseModel):
    candidate: TaskCandidateResponse
    task_id: UUID


class RejectCandidateResponse(BaseModel):
    candidate: TaskCandidateResponse
    undo_expires_at: datetime


class BatchCandidateActionRequest(BaseModel):
    candidate_ids: List[UUID] = Field(min_length=1)


class BatchCandidateItemResult(BaseModel):
    candidate_id: UUID
    status: str
    task_id: Optional[UUID] = None
    message: Optional[str] = None


class BatchCandidateActionResponse(BaseModel):
    results: List[BatchCandidateItemResult]


class ExtractTasksRequest(BaseModel):
    source_type: Literal["text", "url", "email"]
    content: str
    project_id: UUID


class ExtractedTaskResponse(BaseModel):
    title: str
    description: Optional[str]
    priority: Literal["low", "medium", "high"]
    due_date: Optional[date]
    confidence_score: float = Field(ge=0, le=1)


class ExtractTasksResponse(BaseModel):
    source_summary: str
    tasks: List[ExtractedTaskResponse] = Field(default_factory=list)
    created_task_ids: List[UUID] = Field(default_factory=list)


class ExtractJobQueued(BaseModel):
    job_id: UUID
    status: Literal["queued"]


class ExtractJobStatusResponse(BaseModel):
    job_id: UUID
    status: Literal["queued", "running", "done", "failed"]
    attempts: int = 0
    result: Optional[ExtractTasksResponse] = None
    error: Optional[str] = None


class DeadLetterJobResponse(BaseModel):
    job_id: UUID
    project_id: UUID
    reason: str
    last_error: Optional[str] = None
    attempts: int
    created_at: datetime


class RetryDeadLetterRequest(BaseModel):
    project_id: UUID


class AgentLoopEventResponse(BaseModel):
    id: str
    job_id: str
    event_type: str
    iteration: Optional[int] = None
    tool_name: Optional[str] = None
    display_message: str
    message: Optional[str] = None
    output: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    created_at: datetime


class AgentEventsResponse(BaseModel):
    events: List[AgentLoopEventResponse] = Field(default_factory=list)


class RatePoint(BaseModel):
    bucket_start: datetime
    total_actions: int
    accept_rate: float
    reject_rate: float
    edit_rate: float


class FieldAccuracyMetric(BaseModel):
    field: Literal[
        "title",
        "description",
        "priority",
        "due_date",
        "selected_assignee_id",
    ]
    total_considered: int
    accurate_count: int
    accuracy_rate: float


class AssigneeAccuracyMetric(BaseModel):
    total_accepts: int
    top_1_count: int
    top_1_rate: float
    top_2_count: int
    top_2_rate: float
    top_3_count: int
    top_3_rate: float
    not_recommended_count: int
    not_recommended_rate: float
    unassigned_count: int
    unassigned_rate: float


class FeedbackAnalyticsResponse(BaseModel):
    project_id: UUID
    period: Literal["day", "week", "month"]
    rate_series: List[RatePoint]
    field_accuracy: List[FieldAccuracyMetric]
    assignee_accuracy: AssigneeAccuracyMetric


class ProjectForecastResponse(BaseModel):
    velocity_per_week: float
    remaining_tasks: int
    estimated_completion_date: Optional[date] = None
    confidence: Literal["low", "medium", "high"]


class WebhookSubscriptionCreate(BaseModel):
    event_type: str
    target_url: str
    secret: str


class WebhookSubscriptionUpdate(BaseModel):
    event_type: Optional[str] = None
    target_url: Optional[str] = None
    secret: Optional[str] = None
    is_active: Optional[bool] = None


class WebhookSubscriptionResponse(_BaseResponse):
    id: UUID
    workspace_id: UUID
    event_type: str
    target_url: str
    is_active: bool
    created_at: datetime


class WebhookDeliveryResponse(_BaseResponse):
    id: UUID
    subscription_id: UUID
    event_id: UUID
    status: str
    response_code: Optional[int]
    attempted_at: datetime


class WorkspaceMyRoleResponse(_BaseResponse):
    role: str
