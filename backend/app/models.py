import uuid
import enum
from datetime import datetime, date
from sqlalchemy import (
    Column,
    String,
    Text,
    Enum,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Boolean,
    Float,
    Integer,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from app.database import Base


class TaskStatus(enum.Enum):
    todo = "todo"
    in_progress = "in_progress"
    done = "done"
    cancelled = "cancelled"


class TaskPriority(enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class AvailabilityStatus(enum.Enum):
    available = "available"
    busy = "busy"
    on_leave = "on_leave"


class CandidateStatus(enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class CandidateApprovalAction(enum.Enum):
    approve = "approve"
    reject = "reject"
    undo_reject = "undo_reject"


class FeedbackAction(enum.Enum):
    accept = "accept"
    reject = "reject"
    edit = "edit"


class TaskActivityAction(enum.Enum):
    task_created = "task_created"
    status_changed = "status_changed"
    assignment_changed = "assignment_changed"
    field_changed = "field_changed"


class TaskDependencyType(enum.Enum):
    blocks = "blocks"
    relates_to = "relates_to"


class OrgRole(enum.Enum):
    owner = "owner"
    admin = "admin"
    member = "member"


class WorkspaceRole(enum.Enum):
    owner = "owner"
    admin = "admin"
    manager = "manager"
    member = "member"
    viewer = "viewer"


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False, unique=True)
    settings = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class OrgMembership(Base):
    __tablename__ = "org_memberships"

    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    role = Column(String(32), nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_org_memberships_user_id", "user_id"),
        Index("ix_org_memberships_org_id", "org_id"),
    )


class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    owner_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("ix_workspaces_org_id", "org_id"),
        Index("ix_workspaces_owner_id", "owner_id"),
    )


class WorkspaceMembership(Base):
    __tablename__ = "workspace_memberships"

    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    role = Column(String(32), nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_workspace_memberships_user_id", "user_id"),
        Index("ix_workspace_memberships_workspace_id", "workspace_id"),
    )


class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (Index("ix_projects_workspace_id", "workspace_id"),)


class Person(Base):
    __tablename__ = "people"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=True)
    role = Column(String(255), nullable=True)
    skills = Column(ARRAY(String), nullable=True, default=list)
    bio = Column(Text, nullable=True)
    availability = Column(
        Enum(AvailabilityStatus, name="availabilitystatus", create_type=False),
        nullable=True,
    )
    max_capacity = Column(Integer, nullable=False, default=8, server_default="8")
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Task(Base):
    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Enum(TaskStatus), nullable=False, server_default="todo")
    priority = Column(Enum(TaskPriority), nullable=False, server_default="medium")
    due_date = Column(Date, nullable=True)
    assignee_id = Column(
        UUID(as_uuid=True),
        ForeignKey("people.id", ondelete="SET NULL"),
        nullable=True,
    )
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    needs_review = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    archived_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_tasks_status", "status"),
        Index("ix_tasks_priority", "priority"),
        Index("ix_tasks_assignee_id", "assignee_id"),
        Index("ix_tasks_project_id", "project_id"),
        Index("ix_tasks_archived_at", "archived_at"),
    )


class TaskCandidate(Base):
    __tablename__ = "task_candidates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(Enum(TaskPriority), nullable=False, server_default="medium")
    due_date = Column(Date, nullable=True)
    selected_assignee_id = Column(
        UUID(as_uuid=True),
        ForeignKey("people.id", ondelete="SET NULL"),
        nullable=True,
    )
    confidence_score = Column(Float, nullable=False)
    source_type = Column(String(20), nullable=False)
    source_excerpt = Column(Text, nullable=True)
    source_summary = Column(Text, nullable=False)
    assignee_recommendations = Column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    status = Column(
        Enum(CandidateStatus, name="candidatestatus", create_type=False),
        nullable=False,
        server_default="pending",
    )
    approved_task_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at = Column(DateTime(timezone=True), nullable=True)
    rejected_at = Column(DateTime(timezone=True), nullable=True)
    undo_expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index(
            "ix_task_candidates_project_status_created",
            "project_id",
            "status",
            "created_at",
        ),
        Index("ix_task_candidates_status_undo_expires", "status", "undo_expires_at"),
    )


class FeedbackEvent(Base):
    __tablename__ = "feedback_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    candidate_id = Column(
        UUID(as_uuid=True),
        ForeignKey("task_candidates.id", ondelete="CASCADE"),
        nullable=False,
    )
    action = Column(
        Enum(FeedbackAction, name="feedbackaction", create_type=False),
        nullable=False,
    )
    acted_at = Column(DateTime(timezone=True), nullable=False)
    field_deltas = Column(JSONB, nullable=True)
    selected_assignee_id = Column(
        UUID(as_uuid=True),
        ForeignKey("people.id", ondelete="SET NULL"),
        nullable=True,
    )
    selected_assignee_rank = Column(
        String(32),
        nullable=True,
        comment="top_1|top_2|top_3|not_recommended|unassigned",
    )
    # The underlying DB column is named "metadata" (created in migration 005).
    # The Python attribute is event_metadata to avoid shadowing SQLAlchemy internals.
    # To access by table column key use FeedbackEvent.__table__.c["metadata"].
    # A future migration can rename the column to "event_metadata" to remove this alias.
    event_metadata = Column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_feedback_events_project_acted_at", "project_id", "acted_at"),
        Index(
            "ix_feedback_events_project_action_acted_at",
            "project_id",
            "action",
            "acted_at",
        ),
        Index("ix_feedback_events_candidate_acted_at", "candidate_id", "acted_at"),
    )


class TaskActivityEvent(Base):
    __tablename__ = "task_activity_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    action_type = Column(
        Enum(TaskActivityAction, name="taskactivityaction", create_type=False),
        nullable=False,
    )
    field_name = Column(String(64), nullable=True)
    before_value = Column(JSONB, nullable=True)
    after_value = Column(JSONB, nullable=True)
    event_metadata = Column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    actor_type = Column(String(32), nullable=False)
    actor_label = Column(String(255), nullable=True)
    actor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("people.id", ondelete="SET NULL"),
        nullable=True,
    )
    occurred_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_task_activity_events_task_occurred_at", "task_id", "occurred_at"),
        Index(
            "ix_task_activity_events_project_occurred_at",
            "project_id",
            "occurred_at",
        ),
    )


class TaskStatusHistory(Base):
    __tablename__ = "task_status_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_status = Column(String(32), nullable=True)
    to_status = Column(String(32), nullable=False)
    changed_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    changed_by_actor_type = Column(String(32), nullable=False)
    changed_by_actor_id = Column(UUID(as_uuid=True), nullable=True)

    __table_args__ = (
        Index(
            "ix_task_status_history_task_changed_at",
            "task_id",
            "changed_at",
        ),
    )


class TaskEstimate(Base):
    __tablename__ = "task_estimates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    estimated_hours = Column(Float, nullable=True)
    actual_hours = Column(Float, nullable=True)
    estimated_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    recorded_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "ix_task_estimates_task_recorded_at",
            "task_id",
            "recorded_at",
        ),
    )


class Label(Base):
    __tablename__ = "labels"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = Column(String(255), nullable=False)
    color = Column(String(32), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "ix_labels_workspace_id_name",
            "workspace_id",
            "name",
            unique=True,
        ),
    )


class TaskLabel(Base):
    __tablename__ = "task_labels"

    task_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    label_id = Column(
        UUID(as_uuid=True),
        ForeignKey("labels.id", ondelete="CASCADE"),
        primary_key=True,
    )


class TaskDependency(Base):
    __tablename__ = "task_dependencies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dependent_task_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    blocks_task_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    dependency_type = Column(
        Enum(TaskDependencyType, name="taskdependencytype", create_type=False),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_task_dependencies_dependent", "dependent_task_id"),
        Index("ix_task_dependencies_blocks", "blocks_task_id"),
        Index(
            "uq_task_dependencies_edge",
            "dependent_task_id",
            "blocks_task_id",
            "dependency_type",
            unique=True,
        ),
    )


class FeatureEntitlement(Base):
    __tablename__ = "feature_entitlements"

    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    feature_key = Column(String(128), primary_key=True, nullable=False)
    enabled = Column(Boolean, nullable=False, server_default="false")
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_feature_entitlements_org_id", "org_id"),)


class ServiceIdentity(Base):
    __tablename__ = "service_identities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = Column(String(255), nullable=False)
    kind = Column(String(64), nullable=False, server_default="automation_actor")
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_service_identities_org_id", "org_id"),)


class WebhookSubscription(Base):
    __tablename__ = "webhook_subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type = Column(String(64), nullable=False)  # e.g. task.created
    target_url = Column(String(1024), nullable=False)
    secret = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_webhook_subscriptions_workspace_id", "workspace_id"),)


class WebhookDelivery(Base):
    __tablename__ = "webhook_deliveries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subscription_id = Column(
        UUID(as_uuid=True),
        ForeignKey("webhook_subscriptions.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_id = Column(
        UUID(as_uuid=True), nullable=False
    )  # ID of the task/candidate/etc.
    status = Column(String(32), nullable=False)  # e.g. success, failed, retrying
    response_code = Column(Integer)
    attempted_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_webhook_deliveries_subscription_id", "subscription_id"),
    )


class Source(Base):
    __tablename__ = "sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
    )
    source_type = Column(String(32), nullable=False)  # text, url, email, etc.
    title = Column(String(512), nullable=True)
    uri = Column(String(2048), nullable=True)
    content_hash = Column(String(64), nullable=True)
    summary = Column(Text, nullable=True)
    excerpt = Column(Text, nullable=True)
    payload = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_sources_workspace_id", "workspace_id"),
        Index("ix_sources_project_id", "project_id"),
        Index("ix_sources_content_hash", "content_hash"),
    )


class TaskSource(Base):
    __tablename__ = "task_sources"

    task_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    source_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="CASCADE"),
        primary_key=True,
    )
    link_type = Column(
        String(32), nullable=False, server_default="derived_from", primary_key=True
    )
    confidence_score = Column(Float, nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_task_sources_task_id", "task_id"),
        Index("ix_task_sources_source_id", "source_id"),
    )


class TaskCandidateRevision(Base):
    __tablename__ = "task_candidate_revisions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id = Column(
        UUID(as_uuid=True),
        ForeignKey("task_candidates.id", ondelete="CASCADE"),
        nullable=False,
    )
    revision_number = Column(Integer, nullable=False)
    revision_type = Column(String(32), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(Enum(TaskPriority), nullable=False)
    due_date = Column(Date, nullable=True)
    selected_assignee_id = Column(
        UUID(as_uuid=True),
        ForeignKey("people.id", ondelete="SET NULL"),
        nullable=True,
    )
    confidence_score = Column(Float, nullable=False)
    source_type = Column(String(20), nullable=False)
    source_excerpt = Column(Text, nullable=True)
    source_summary = Column(Text, nullable=False)
    model_version = Column(String(128), nullable=True)
    prompt_template_hash = Column(String(64), nullable=True)
    model_latency_ms = Column(Integer, nullable=True)
    event_metadata = Column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "ix_task_candidate_revisions_candidate_created",
            "candidate_id",
            "created_at",
        ),
        Index(
            "uq_task_candidate_revisions_candidate_number",
            "candidate_id",
            "revision_number",
            unique=True,
        ),
    )


class CandidateSourceSpan(Base):
    __tablename__ = "candidate_source_spans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_revision_id = Column(
        UUID(as_uuid=True),
        ForeignKey("task_candidate_revisions.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    span_start = Column(Integer, nullable=True)
    span_end = Column(Integer, nullable=True)
    snippet = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "ix_candidate_source_spans_revision_id",
            "candidate_revision_id",
        ),
        Index("ix_candidate_source_spans_source_id", "source_id"),
    )


class CandidateApprovalEvent(Base):
    __tablename__ = "candidate_approval_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id = Column(
        UUID(as_uuid=True),
        ForeignKey("task_candidates.id", ondelete="CASCADE"),
        nullable=False,
    )
    task_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
    )
    action = Column(
        Enum(
            CandidateApprovalAction,
            name="candidateapprovalaction",
            create_type=False,
        ),
        nullable=False,
    )
    actor_type = Column(String(32), nullable=False)
    actor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_metadata = Column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index(
            "ix_candidate_approval_events_candidate_created",
            "candidate_id",
            "created_at",
        ),
        Index("ix_candidate_approval_events_task_id", "task_id"),
    )


class MemoryAuditEvent(Base):
    __tablename__ = "memory_audit_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=False)
    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="SET NULL"),
        nullable=True,
    )
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
    )
    action = Column(String(32), nullable=False)
    actor_type = Column(String(32), nullable=False)
    actor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    query_hash = Column(String(128), nullable=True)
    result_count = Column(Integer, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    status = Column(String(32), nullable=False)
    event_metadata = Column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_memory_audit_events_org_created", "org_id", "created_at"),
        Index(
            "ix_memory_audit_events_workspace_created",
            "workspace_id",
            "created_at",
        ),
        Index("ix_memory_audit_events_project_created", "project_id", "created_at"),
        Index("ix_memory_audit_events_action_created", "action", "created_at"),
    )


class TaskComment(Base):
    __tablename__ = "task_comments"

    # PK — UUID, matches all existing tables
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # task FK — CASCADE delete (comment deleted with task)
    task_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
    )

    # author FK — SET NULL on user deletion (per D-05, matches actor_id pattern in TaskActivityEvent)
    # author_id → users.id (per D-01; NOT people.id — Person is for task assignment, not auth users)
    author_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # body — Text (matches Task.description, Project.description; no length limit at DB level)
    body = Column(Text, nullable=False)

    # edited_at — nullable DateTime, NOT a boolean (per D-04; matches archived_at/approved_at convention)
    # Phase 2 derives is_edited as `edited_at IS NOT NULL`
    edited_at = Column(DateTime(timezone=True), nullable=True)

    # created_at — timezone-aware, server default
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # updated_at — set on body edits (optional per agent discretion; include for completeness)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        # Composite index: chronological listing per task (primary query pattern)
        Index("ix_task_comments_task_id_created_at", "task_id", "created_at"),
        # Single-column index on author_id (per D-03: every FK gets an index)
        Index("ix_task_comments_author_id", "author_id"),
    )
