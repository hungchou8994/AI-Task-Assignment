# Backend API Reference

## Base URL

- **Docker / Production:** `http://localhost:8000`
- **PM2 deploy:** `http://localhost:8003`
- All endpoints are prefixed with `/api`

## Authentication

The API uses **session-based authentication** (signed cookies via `itsdangerous`).

| Endpoint | Method | Description |
|---|---|---|
| `/api/auth/register` | POST | Create a new user account |
| `/api/auth/login` | POST | Log in and create a session |
| `/api/auth/logout` | POST | Destroy the session |
| `/api/auth/me` | GET | Get the currently authenticated user |

**Request body for login/register:**
```json
{
  "email": "user@example.com",
  "password": "secret"
}
```

---

## Health Check

| Endpoint | Method | Description |
|---|---|---|
| `/api/health` | GET | Returns `{ "status": "ok" }` |

---

## Workspaces & Projects

All task data is scoped to a workspace. Most endpoints require a workspace member role.

### Workspaces

| Endpoint | Method | Description |
|---|---|---|
| `/api/workspaces` | GET | List workspaces for the current user |
| `/api/workspaces` | POST | Create a new workspace |
| `/api/workspaces/{workspace_id}` | GET | Get a workspace |
| `/api/workspaces/{workspace_id}` | PATCH | Update workspace name |
| `/api/workspaces/{workspace_id}/members` | GET | List workspace members |
| `/api/workspaces/{workspace_id}/members` | POST | Add a member |
| `/api/workspaces/{workspace_id}/members/{user_id}` | PATCH | Update member role |
| `/api/workspaces/{workspace_id}/members/{user_id}` | DELETE | Remove a member |

### Projects

| Endpoint | Method | Description |
|---|---|---|
| `/api/workspaces/{workspace_id}/projects` | GET | List projects |
| `/api/workspaces/{workspace_id}/projects` | POST | Create a project |
| `/api/workspaces/{workspace_id}/projects/{project_id}` | GET | Get a project |
| `/api/workspaces/{workspace_id}/projects/{project_id}` | PATCH | Update a project |
| `/api/workspaces/{workspace_id}/projects/{project_id}` | DELETE | Archive a project |

### Labels

| Endpoint | Method | Description |
|---|---|---|
| `/api/workspaces/{workspace_id}/labels` | GET | List labels |
| `/api/workspaces/{workspace_id}/labels` | POST | Create a label |
| `/api/workspaces/{workspace_id}/labels/{label_id}` | PATCH | Update a label |
| `/api/workspaces/{workspace_id}/labels/{label_id}` | DELETE | Delete a label |

---

## Tasks

| Endpoint | Method | Description |
|---|---|---|
| `/api/workspaces/{workspace_id}/tasks` | GET | List tasks (filterable by project, status, priority, assignee, archived) |
| `/api/workspaces/{workspace_id}/tasks` | POST | Create a task |
| `/api/workspaces/{workspace_id}/tasks/{task_id}` | GET | Get a task |
| `/api/workspaces/{workspace_id}/tasks/{task_id}` | PATCH | Update a task |
| `/api/workspaces/{workspace_id}/tasks/{task_id}` | DELETE | Delete a task |
| `/api/workspaces/{workspace_id}/tasks/{task_id}/archive` | POST | Archive a task |
| `/api/workspaces/{workspace_id}/tasks/{task_id}/unarchive` | POST | Unarchive a task |
| `/api/workspaces/{workspace_id}/tasks/{task_id}/labels` | POST | Add a label to a task |
| `/api/workspaces/{workspace_id}/tasks/{task_id}/labels/{label_id}` | DELETE | Remove a label from a task |
| `/api/workspaces/{workspace_id}/tasks/{task_id}/dependencies` | POST | Add a dependency |
| `/api/workspaces/{workspace_id}/tasks/{task_id}/dependencies/{dep_id}` | DELETE | Remove a dependency |
| `/api/workspaces/{workspace_id}/tasks/{task_id}/provenance` | GET | Get source provenance for a task |

**Task create/update body example:**
```json
{
  "title": "Implement login page",
  "description": "Create the login form with email/password fields",
  "status": "todo",
  "priority": "high",
  "assignee_id": "uuid",
  "due_date": "2026-05-01",
  "project_id": "uuid"
}
```

---

## Task Activity

| Endpoint | Method | Description |
|---|---|---|
| `/api/workspaces/{workspace_id}/tasks/{task_id}/activity` | GET | Get activity events for a task |
| `/api/workspaces/{workspace_id}/tasks/{task_id}/status-history` | GET | Get status transition history |

---

## People (Team Members)

| Endpoint | Method | Description |
|---|---|---|
| `/api/workspaces/{workspace_id}/people` | GET | List people |
| `/api/workspaces/{workspace_id}/people` | POST | Create a person |
| `/api/workspaces/{workspace_id}/people/{person_id}` | GET | Get a person |
| `/api/workspaces/{workspace_id}/people/{person_id}` | PATCH | Update a person |
| `/api/workspaces/{workspace_id}/people/{person_id}` | DELETE | Delete a person |

**Person body example:**
```json
{
  "name": "Alice Smith",
  "email": "alice@example.com",
  "role": "Backend Engineer",
  "skills": "Python, FastAPI, PostgreSQL, Docker",
  "availability": "full-time"
}
```

---

## AI Extraction

| Endpoint | Method | Description |
|---|---|---|
| `/api/ai/extract` | POST | Submit content for AI extraction (returns job_id) |
| `/api/ai/jobs/{job_id}` | GET | Get job status and result |
| `/api/ai/jobs/{job_id}/events` | GET | SSE stream of agent events (real-time) |
| `/api/ai/jobs/{job_id}/dead-letter/retry` | POST | Retry a failed job from the dead-letter queue |
| `/api/ai/jobs` | GET | List recent jobs |

**Extraction request body:**
```json
{
  "content": "Please build a login page and set up the database migration by Friday.",
  "content_type": "text",
  "project_id": "uuid",
  "workspace_id": "uuid"
}
```

**Content types:** `"text"` | `"url"` | `"email"`

**Job status response:**
```json
{
  "job_id": "uuid",
  "status": "completed",
  "result": {
    "tasks": [
      {
        "id": "uuid",
        "title": "Build login page",
        "description": "...",
        "priority": "high",
        "due_date": "2026-05-02",
        "assignee_recommendations": [...]
      }
    ]
  },
  "error": null,
  "created_at": "...",
  "updated_at": "..."
}
```

**SSE event types (streaming):**
- `thinking_delta` — model reasoning token
- `text_delta` — model text output token
- `tool_call` — agent is calling a tool
- `tool_result` — tool returned a result
- `finalized` — extraction complete
- `error` — pipeline error

---

## Task Candidates (Review Queue)

| Endpoint | Method | Description |
|---|---|---|
| `/api/workspaces/{workspace_id}/candidates` | GET | List pending candidates |
| `/api/workspaces/{workspace_id}/candidates/{candidate_id}` | GET | Get a candidate |
| `/api/workspaces/{workspace_id}/candidates/{candidate_id}` | PATCH | Edit a candidate |
| `/api/workspaces/{workspace_id}/candidates/{candidate_id}/approve` | POST | Approve a candidate |
| `/api/workspaces/{workspace_id}/candidates/{candidate_id}/reject` | POST | Reject a candidate |
| `/api/workspaces/{workspace_id}/candidates/{candidate_id}/undo` | POST | Undo approve or reject |
| `/api/workspaces/{workspace_id}/candidates/batch/approve` | POST | Batch approve |
| `/api/workspaces/{workspace_id}/candidates/batch/reject` | POST | Batch reject |
| `/api/workspaces/{workspace_id}/candidates/{candidate_id}/revisions` | GET | Get revision history |

---

## Sources

| Endpoint | Method | Description |
|---|---|---|
| `/api/workspaces/{workspace_id}/sources` | GET | List source documents |
| `/api/workspaces/{workspace_id}/sources/{source_id}` | GET | Get a source document |

---

## Feedback Analytics

| Endpoint | Method | Description |
|---|---|---|
| `/api/workspaces/{workspace_id}/analytics/feedback` | GET | Aggregated AI feedback metrics |
| `/api/workspaces/{workspace_id}/analytics/feedback/timeline` | GET | Approval/rejection timeline |

---

## Webhooks

| Endpoint | Method | Description |
|---|---|---|
| `/api/workspaces/{workspace_id}/webhooks` | GET | List webhook subscriptions |
| `/api/workspaces/{workspace_id}/webhooks` | POST | Create a webhook subscription |
| `/api/workspaces/{workspace_id}/webhooks/{webhook_id}` | GET | Get a subscription |
| `/api/workspaces/{workspace_id}/webhooks/{webhook_id}` | PATCH | Update a subscription |
| `/api/workspaces/{workspace_id}/webhooks/{webhook_id}` | DELETE | Delete a subscription |
| `/api/workspaces/{workspace_id}/webhooks/{webhook_id}/deliveries` | GET | List recent deliveries |

**Webhook subscription body:**
```json
{
  "url": "https://example.com/webhook",
  "events": ["task.created", "task.updated", "task.status_changed"],
  "secret": "optional-signing-secret"
}
```

---

## Error Responses

All errors follow a consistent format:

```json
{
  "detail": "Human-readable error message"
}
```

| HTTP Status | Meaning |
|---|---|
| `400` | Bad request / validation error |
| `401` | Not authenticated |
| `403` | Not authorized (insufficient role) |
| `404` | Resource not found |
| `409` | Conflict (e.g., duplicate) |
| `422` | Pydantic validation error |
| `500` | Internal server error |
