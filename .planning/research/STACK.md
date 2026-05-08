# Stack Research: Task Comments Brownfield Feature

**Project:** AI Task Management Platform — Task Comments  
**Dimension:** Stack-level implementation choices only  
**Researched:** 2026-05-05  
**Overall confidence:** HIGH for repository fit; MEDIUM for exact line placement until implementation touches files.

## Recommendation

Add task comments as a small first-party CRUD feature using the existing stack only: FastAPI routers + dependency auth, SQLAlchemy ORM + Alembic migration, PostgreSQL UUID/text/timestamp columns, React + TypeScript typed API wrappers, and TanStack Query query/mutation hooks. Do **not** add a comment SDK, realtime transport, markdown editor, rich-text editor, sanitizer dependency, websocket layer, notification system, or separate state manager.

This repository already has everything needed for v1 comments:

| Need | Use | Why |
|---|---|---|
| API routing | FastAPI `APIRouter` | Existing backend routers use one domain router per file and include routers in `backend/app/main.py`. |
| Auth/permissions | Existing `get_current_user`, `ensure_task_access`, `ensure_workspace_access` patterns | Requirement explicitly needs backend-enforced permissions; repo already centralizes session auth in `backend/app/auth.py`. |
| Persistence | SQLAlchemy model in `backend/app/models.py` + Alembic migration | Existing schema changes are plain Alembic migrations with reversible downgrades. |
| Data validation | Pydantic schemas in `backend/app/schemas.py` or route-local payload classes | Existing responses use `ConfigDict(from_attributes=True)` for ORM serialization. |
| Frontend data fetching | Existing `frontend/src/api/tasks.ts` + `frontend/src/hooks/useTasks.ts` | TanStack Query v5 docs and repo conventions use `useQuery`, `useMutation`, and `invalidateQueries`. |
| UI | Plain React component under `frontend/src/components/tasks/` | `TaskModal.tsx` already hosts activity and sources sections; comments fit as another task-detail section. |
| i18n | `frontend/src/i18n/translations.ts` | Must support English and Japanese; existing UI reads labels through `useLanguage()`. |

## Dependency Decision

### Add no runtime dependencies

No new backend or frontend packages are recommended.

| Potential dependency | Decision | Reason |
|---|---|---|
| Markdown renderer / editor | Do not add | Existing project already has `react-markdown`, `remark-gfm`, and `dompurify`, but milestone scopes comments as plain text. Rendering user comments as plain text avoids XSS and review complexity. |
| Rich text editor (`tiptap`, `slate`, `lexical`, etc.) | Do not add | Over-scoped for 2–3 days and adds serialization/sanitization decisions. |
| WebSockets/SSE | Do not add | Realtime cross-browser updates are out of scope; React Query invalidation after mutations is enough. |
| Zustand/Redux/Jotai | Do not add | Comments are server state, not app-global client state. TanStack Query already owns this pattern. |
| Pagination/infinite query helpers | Do not add for MVP | Pagination/load-more is explicitly optional. Keep list simple and chronological for v1. |
| Mention autocomplete libraries | Do not add | `@mention` support is optional and creates member search, notifications, parsing, and permission edge cases. |

## Backend Implementation Choices

### Data model

Add a dedicated `TaskComment` ORM model in `backend/app/models.py`.

Recommended columns:

| Column | Type | Null | Default | Purpose |
|---|---|---:|---|---|
| `id` | `UUID(as_uuid=True)` | no | `uuid.uuid4` | Stable comment identifier. |
| `task_id` | FK `tasks.id` `ON DELETE CASCADE` | no | — | Comments belong to a task and should be removed when the task is hard-deleted. |
| `author_id` | FK `users.id` `ON DELETE SET NULL` | yes | — | Identifies edit/delete ownership while user exists. Nullable preserves comments if a user is deleted later. |
| `author_email_snapshot` | `String(255)` | no | — | Ensures UI can still display an author if `author_id` becomes null. |
| `content` | `Text` | no | — | Plain-text comment body. Validate trimmed non-empty content in API schemas. |
| `created_at` | `DateTime(timezone=True)` | no | `func.now()` | Thread ordering and display. |
| `updated_at` | `DateTime(timezone=True)` | no | `func.now()`, `onupdate=func.now()` | API freshness and debugging. |
| `edited_at` | `DateTime(timezone=True)` | yes | — | UI can show an explicit “edited” marker without inferring from `updated_at`. |

Recommended indexes:

```python
Index("ix_task_comments_task_created", "task_id", "created_at"),
Index("ix_task_comments_author_id", "author_id"),
```

Use chronological ordering by `created_at.asc(), id.asc()` for stable thread order. This matches the product requirement and avoids needing pagination or cursor design in v1.

Do **not** denormalize `workspace_id` onto `task_comments` for MVP. Permission checks can resolve workspace through `Task -> Project -> Workspace` using existing helpers. Denormalizing workspace would speed admin queries but adds consistency risk and is unnecessary for comment lists scoped by one task.

### Migration

Create a new Alembic migration after `014_memory_audit_events`, likely:

`backend/alembic/versions/015_task_comments.py`

Migration should create `task_comments`, add the two indexes above, and downgrade by dropping indexes then the table. No PostgreSQL enum is needed because v1 has no comment state machine.

### API shape

Use nested task routes under `/api/tasks` to match existing task activity and sources routes.

Recommended router file:

`backend/app/routers/task_comments.py`

Recommended routes:

| Method | Path | Response | Permission |
|---|---|---|---|
| `GET` | `/api/tasks/{task_id}/comments` | `list[TaskCommentResponse]` | `ensure_task_access(..., min_role="viewer")` |
| `POST` | `/api/tasks/{task_id}/comments` | `TaskCommentResponse`, `201` | `ensure_task_access(..., min_role="member")` |
| `PUT` | `/api/tasks/{task_id}/comments/{comment_id}` | `TaskCommentResponse` | author only; also require task visibility |
| `DELETE` | `/api/tasks/{task_id}/comments/{comment_id}` | `204` | author OR workspace `admin`/`owner`; enforce on backend |

Add router include in `backend/app/main.py`. Use `APIRouter(prefix="/api/tasks", tags=["task-comments"])`, matching `backend/app/routers/task_activity.py`.

### Schemas

Add API schemas in `backend/app/schemas.py` unless implementation chooses route-local payload classes to match the newest router convention:

```python
class TaskCommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=5000)

class TaskCommentUpdate(BaseModel):
    content: str = Field(min_length=1, max_length=5000)

class TaskCommentResponse(_BaseResponse):
    id: UUID
    task_id: UUID
    author_id: UUID | None
    author_email: str
    content: str
    created_at: datetime
    updated_at: datetime
    edited_at: datetime | None
```

Trim whitespace before persistence. Pydantic `min_length=1` rejects an empty string but not whitespace-only content unless the code strips first.

### Permission helpers

Keep permission logic near `task_comments.py` unless it becomes reusable. Recommended helpers:

- `_get_comment_for_task(db, task_id, comment_id)` — ensure comment belongs to task; return 404 otherwise.
- `_task_workspace_id(db, task)` — copy or reuse the same pattern from `backend/app/routers/tasks.py`.
- `_can_delete_any_comment(db, task, current_user)` — true for workspace owner/admin, workspace owner field, and existing org owner/admin full-access pattern if desired.

Important: edit should be author-only. Admin delete does **not** imply admin edit unless product explicitly asks for moderation edits.

### Activity timeline and webhooks

Do not integrate comments into `TaskActivityEvent` for MVP. The candidate brief lists activity timeline integration as nice-to-have. Adding `comment_created` to `TaskActivityAction` would require a PostgreSQL enum migration and UI label changes; this is unnecessary risk for the must-have feature.

Do not dispatch webhooks or Telegram notifications for comments in v1. Existing webhook events are task-oriented and comment notifications are out of scope.

## Frontend Implementation Choices

### Types

Update `frontend/src/types.ts`:

```ts
export interface TaskComment {
  id: string;
  task_id: string;
  author_id: string | null;
  author_email: string;
  content: string;
  created_at: string;
  updated_at: string;
  edited_at: string | null;
}

export interface TaskCommentCreate { content: string; }
export interface TaskCommentUpdate { content: string; }
```

Use `author_email` from the API instead of joining users in the frontend. The current frontend has authenticated user context but no general user lookup hook for arbitrary comment authors.

### API module

Extend `frontend/src/api/tasks.ts` with thin wrappers:

```ts
export const fetchTaskComments = (taskId: string) =>
  api.get<TaskComment[]>(`/api/tasks/${taskId}/comments`);
export const createTaskComment = (taskId: string, data: TaskCommentCreate) =>
  api.post<TaskComment>(`/api/tasks/${taskId}/comments`, data);
export const updateTaskComment = (taskId: string, commentId: string, data: TaskCommentUpdate) =>
  api.put<TaskComment>(`/api/tasks/${taskId}/comments/${commentId}`, data);
export const deleteTaskComment = (taskId: string, commentId: string) =>
  api.delete(`/api/tasks/${taskId}/comments/${commentId}`);
```

Keep API wrappers free of UI logic, toasts, and permission branching.

### React Query hooks

Extend `frontend/src/hooks/useTasks.ts`:

```ts
export const TASK_COMMENTS_KEY = ['task-comments'] as const;
```

Recommended hooks:

- `useTaskComments(taskId: string | null)` with `enabled: !!taskId`, `staleTime: 30_000`
- `useCreateTaskComment()` invalidates `[..., taskId]`
- `useUpdateTaskComment()` invalidates `[..., taskId]`
- `useDeleteTaskComment()` invalidates `[..., taskId]`

Use TanStack Query invalidation rather than optimistic UI for MVP. TanStack Query docs confirm mutation `onSuccess` plus `queryClient.invalidateQueries({ queryKey })` is the standard cache refresh pattern, and the repository already uses that pattern for tasks and task activity.

### UI component structure

Create a focused component instead of growing `TaskModal.tsx` further:

`frontend/src/components/tasks/TaskComments.tsx`

`TaskModal.tsx` should import and render it near the existing sources/activity sections, preferably between task details and activity timeline:

```tsx
<TaskComments taskId={task.id} />
```

Recommended UI behaviors:

- List comments chronologically oldest-first.
- Show loading, empty, and error states.
- Use a plain `<textarea>` for new and edit forms.
- Disable submit while mutation is pending.
- Trim content client-side before mutate; backend still validates independently.
- Show `author_email`, formatted timestamp, and an “edited” marker when `edited_at` is present.
- Render comment content as text in a normal element (`white-space: pre-wrap` via Tailwind `whitespace-pre-wrap`) rather than markdown/HTML.
- Use `useAuth()` if available to decide whether to show author edit/delete controls. Treat this as UI convenience only; backend remains authoritative.

The frontend cannot reliably know admin/owner delete permission from current visible data unless workspace role is already exposed by context. Do not overbuild a permissions client. It is acceptable to show delete only for own comments in v1 UI, or show delete and let backend reject with an error if current UI patterns already do that. If role data is available in `WorkspaceContext`, use it; do not create a new permissions API just for this feature.

### i18n

Update both English and Japanese sections in `frontend/src/i18n/translations.ts`, under `taskModal` or a new `taskComments` group. Required keys:

- `comments`
- `loadingComments`
- `noComments`
- `addComment`
- `commentPlaceholder`
- `postingComment`
- `editComment`
- `saveComment`
- `savingComment`
- `deleteComment`
- `confirmDeleteComment`
- `edited`
- `commentError`

Do not hard-code English labels inside `TaskComments.tsx`.

## Files Likely Affected

### Backend

| File | Change |
|---|---|
| `backend/app/models.py` | Add `TaskComment` model and indexes. |
| `backend/app/schemas.py` | Add create/update/response schemas. |
| `backend/app/routers/task_comments.py` | New CRUD router for comments. |
| `backend/app/main.py` | Import/include `task_comments.router`. |
| `backend/alembic/versions/015_task_comments.py` | New reversible migration. |
| `backend/tests/...` if tests exist | Add focused API permission tests if practical. |

### Frontend

| File | Change |
|---|---|
| `frontend/src/types.ts` | Add comment interfaces. |
| `frontend/src/api/tasks.ts` | Add comment API functions. |
| `frontend/src/hooks/useTasks.ts` | Add query key and comment hooks. |
| `frontend/src/components/tasks/TaskComments.tsx` | New component for list/form/edit/delete. |
| `frontend/src/components/tasks/TaskModal.tsx` | Render `TaskComments`. |
| `frontend/src/i18n/translations.ts` | Add English/Japanese strings. |

## What Not To Add

- Do not add markdown/rich-text support for v1.
- Do not add WebSocket/SSE realtime updates.
- Do not add comment pagination unless must-haves are complete and verified.
- Do not add notifications, webhook events, or activity-timeline enum changes for comments in the first pass.
- Do not add client-only permission enforcement as a substitute for backend checks.
- Do not create a separate `comments` top-level API namespace; comments are task-scoped in this product.
- Do not store rendered HTML. Store plain text only.
- Do not soft-delete comments unless product asks for auditability. Hard delete is simpler and matches the brief wording.

## Validation Checklist for Implementation

- Backend rejects whitespace-only comments.
- Backend verifies task access on every route.
- Backend verifies comment belongs to the task path parameter.
- Author can edit own comment.
- Non-author cannot edit comment.
- Author can delete own comment.
- Workspace admin/owner can delete another user's comment.
- Viewer can read comments but cannot create comments.
- Deleting a task cascades comments through the database FK.
- Frontend handles empty/loading/error states.
- Frontend strings exist in English and Japanese.
- React Query invalidates comments after create/update/delete.

## Sources

- Repository context: `.planning/PROJECT.md`, `candidate-task.md`, `.planning/codebase/STACK.md`, `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/CONVENTIONS.md`.
- Repository code: `backend/app/models.py`, `backend/app/routers/tasks.py`, `backend/app/routers/task_activity.py`, `backend/app/auth.py`, `backend/alembic/versions/006_task_activity_events.py`, `frontend/src/api/tasks.ts`, `frontend/src/hooks/useTasks.ts`, `frontend/src/components/tasks/TaskModal.tsx`, `frontend/src/types.ts`, `frontend/src/i18n/translations.ts`.
- Context7 FastAPI docs (`/fastapi/fastapi`): `response_model`, `status_code`, and APIRouter patterns are current and consistent with existing code.
- Context7 SQLAlchemy ORM docs (`/websites/sqlalchemy_en_20_orm`): `ON DELETE CASCADE`, relationship/delete behavior, and `order_by` behavior support the proposed model and ordering.
- Context7 TanStack Query docs (`/tanstack/query`): `useMutation` + `queryClient.invalidateQueries({ queryKey })` is the recommended mutation refresh pattern and matches this repo.
