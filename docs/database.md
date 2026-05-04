# Database Schema

## Overview

The database is **PostgreSQL 16**, managed by **Alembic** for schema migrations. The schema has evolved through 14 sequential migrations, each adding a coherent set of features.

## Entity Relationship Summary

```
Organization
  ├── OrgMembership (users ↔ organizations, with roles)
  └── Workspace
        ├── WorkspaceMembership (users ↔ workspaces, with roles)
        ├── Label
        ├── WebhookSubscription → WebhookDelivery
        ├── FeatureEntitlement
        └── Project
              ├── Task
              │     ├── TaskLabel (→ Label)
              │     ├── TaskDependency (self-referencing)
              │     ├── TaskEstimate
              │     ├── TaskSource (→ Source)
              │     ├── TaskActivityEvent
              │     └── TaskStatusHistory
              ├── TaskCandidate
              │     ├── TaskCandidateRevision
              │     ├── CandidateSourceSpan (→ Source)
              │     └── CandidateApprovalEvent
              └── Source
                    └── TaskSource (→ Task)
```

## Model Reference

### `User`
Authenticated user accounts.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `email` | String, unique | Login identifier |
| `hashed_password` | String | bcrypt |
| `name` | String | Display name |
| `created_at` | DateTime | |

---

### `Organization` / `OrgMembership`
Top-level tenant container.

**Organization:** `id`, `name`, `created_at`

**OrgMembership:** `user_id`, `org_id`, `role` (`owner` / `admin` / `member`)

---

### `Workspace` / `WorkspaceMembership`
Scoped within an organization.

**Workspace:** `id`, `name`, `org_id (FK)`, `created_at`

**WorkspaceMembership:** `user_id`, `workspace_id`, `role` (`owner` / `admin` / `manager` / `member` / `viewer`)

---

### `Project`
Container for tasks within a workspace.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `workspace_id` | FK | |
| `name` | String | |
| `description` | Text | |
| `status` | Enum | `active` / `archived` |
| `created_at` | DateTime | |

---

### `Person`
Team member profile used for assignee recommendations.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `workspace_id` | FK | |
| `name` | String | |
| `email` | String | |
| `role` | String | Job title / role |
| `skills` | Text | Free-text skills description |
| `availability` | String | e.g., "full-time", "part-time" |
| `created_at` | DateTime | |

---

### `Task`
Core task record.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `project_id` | FK | |
| `workspace_id` | FK | |
| `title` | String | |
| `description` | Text | |
| `status` | Enum | `todo` / `in_progress` / `done` / `cancelled` |
| `priority` | Enum | `low` / `medium` / `high` / `urgent` |
| `assignee_id` | FK → Person | Nullable |
| `due_date` | Date | Nullable |
| `is_ai_generated` | Boolean | True if created by extraction agent |
| `is_archived` | Boolean | |
| `created_by` | FK → User | Nullable |
| `created_at` | DateTime | |
| `updated_at` | DateTime | |

---

### `TaskCandidate`
AI-extracted task pending human review.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `task_id` | FK → Task | The promoted task (if approved) |
| `project_id` | FK | |
| `source_id` | FK → Source | |
| `title` | String | Editable before approval |
| `description` | Text | |
| `priority` | Enum | |
| `due_date` | Date | Nullable |
| `assignee_id` | FK → Person | Nullable |
| `assignee_recommendations` | JSONB | `[{person_id, confidence, reasoning}]` |
| `status` | Enum | `pending` / `approved` / `rejected` |
| `created_at` | DateTime | |

---

### `TaskCandidateRevision`
Immutable revision history for each candidate.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `candidate_id` | FK | |
| `snapshot` | JSONB | Full candidate state at that revision |
| `revision_type` | Enum | `created` / `edited` / `approved` / `rejected` / `undone` |
| `author_id` | FK → User | Nullable (null = AI) |
| `created_at` | DateTime | |

---

### `CandidateSourceSpan`
Character-level provenance linking a candidate to a position in its source document.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `candidate_id` | FK | |
| `source_id` | FK | |
| `start_char` | Integer | |
| `end_char` | Integer | |
| `span_text` | Text | Extracted snippet |

---

### `CandidateApprovalEvent`
Audit log of every approve/reject/undo action.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `candidate_id` | FK | |
| `action` | Enum | `approved` / `rejected` / `undone` |
| `actor_id` | FK → User | |
| `created_at` | DateTime | |

---

### `Source`
A source document submitted for AI extraction.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `project_id` | FK | |
| `workspace_id` | FK | |
| `content` | Text | Raw or fetched content |
| `content_type` | Enum | `text` / `url` / `email` |
| `content_hash` | String | SHA-256; used for deduplication |
| `original_url` | String | Nullable (for URL sources) |
| `submitted_by` | FK → User | Nullable |
| `created_at` | DateTime | |

---

### `TaskSource`
Many-to-many link between `Task` and `Source`.

| Column | Type |
|---|---|
| `task_id` | FK → Task |
| `source_id` | FK → Source |

---

### `FeedbackEvent`
Records every human review decision for analytics.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `task_id` | FK → Task | Nullable |
| `candidate_id` | FK → TaskCandidate | Nullable |
| `action` | String | `approved` / `rejected` / `edited` |
| `actor_id` | FK → User | |
| `created_at` | DateTime | |

---

### `TaskActivityEvent`
Field-level change log for tasks.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `task_id` | FK | |
| `actor_id` | FK → User | Nullable |
| `field` | String | e.g., `"status"`, `"assignee_id"` |
| `old_value` | Text | Nullable |
| `new_value` | Text | Nullable |
| `created_at` | DateTime | |

---

### `TaskStatusHistory`
Dedicated timeline of status transitions.

| Column | Type |
|---|---|
| `id` | UUID PK |
| `task_id` | FK |
| `old_status` | Enum |
| `new_status` | Enum |
| `actor_id` | FK → User |
| `changed_at` | DateTime |

---

### `TaskEstimate`
Effort estimate attached to a task.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `task_id` | FK (unique) | One estimate per task |
| `estimated_hours` | Float | |
| `created_at` | DateTime | |

---

### `Label` / `TaskLabel`
Tagging system.

**Label:** `id`, `workspace_id`, `name`, `color`

**TaskLabel:** `task_id`, `label_id` (composite PK)

---

### `TaskDependency`
Directed dependency graph between tasks.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `source_task_id` | FK | The blocking/related task |
| `target_task_id` | FK | The task being blocked/related |
| `dependency_type` | Enum | `blocks` / `relates_to` |

---

### `WebhookSubscription` / `WebhookDelivery`

**WebhookSubscription:** `id`, `workspace_id`, `url`, `events` (JSONB array), `secret`, `is_active`, `created_at`

**WebhookDelivery:** `id`, `subscription_id`, `event_type`, `payload` (JSONB), `status` (pending/delivered/failed), `response_status`, `attempted_at`

---

### `MemoryAuditEvent`
Audit trail for MemPalace memory operations.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `workspace_id` | FK | |
| `operation` | String | `store` / `retrieve` / `forget` |
| `memory_key` | String | |
| `details` | JSONB | |
| `created_at` | DateTime | |

---

### `FeatureEntitlement`
Per-organization feature flags.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `org_id` | FK | |
| `feature` | String | Feature key |
| `enabled` | Boolean | |

---

### `ServiceIdentity`
Machine actor identities for automation (e.g., the AI agent itself).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `workspace_id` | FK | |
| `name` | String | e.g., `"AI Extraction Agent"` |
| `api_key_hash` | String | |
| `created_at` | DateTime | |

---

## Migration History

| # | Name | What it introduces |
|---|---|---|
| 001 | `initial_schema` | Core: tasks, people, basic tables |
| 002 | `ai_layer_fields` | AI-related columns on task/candidate tables |
| 003 | `workspace_project` | Workspace + Project hierarchy |
| 004 | `task_candidates_review_queue` | `task_candidates` table + review workflow |
| 005 | `feedback_events_analytics` | `feedback_events` for AI accuracy analytics |
| 006 | `task_activity_events` | Activity log + status history |
| 007 | `add_user_and_workspace_owner` | User auth model + workspace ownership |
| 008 | `add_cancelled_task_status` | `cancelled` value to status enum |
| 009 | `multi_tenant_rbac` | Organization, OrgMembership, WorkspaceMembership, RBAC roles |
| 010 | `task_schema_extensions` | Labels, TaskLabel, TaskDependency, TaskEstimate, ServiceIdentity, FeatureEntitlement |
| 011 | `add_webhook_tables` | WebhookSubscription, WebhookDelivery |
| 012 | `task_sources_n2n` | `sources` table + `task_sources` N:M join table |
| 013 | `candidate_provenance_graph` | TaskCandidateRevision, CandidateSourceSpan, CandidateApprovalEvent |
| 014 | `memory_audit_events` | MemoryAuditEvent for memory integration tracking |

## Running Migrations

```bash
# Apply all pending migrations
cd backend
alembic upgrade head

# Roll back one migration
alembic downgrade -1

# Show current migration state
alembic current

# Show full history
alembic history
```
