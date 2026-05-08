# Architecture Research: Task Comments

**Project:** AI Task Management Platform — Task Comments  
**Researched:** 2026-05-05  
**Dimension:** Brownfield architecture integration  
**Overall confidence:** HIGH for repository fit; MEDIUM for exact implementation details until tests confirm current branch behavior

## Recommendation

Add Task Comments as a small task-scoped domain that follows the existing `/api/tasks/{task_id}/...` subresource pattern already used for activity, sources, dependencies, and assignee recommendations. The backend should add a `TaskComment` ORM model in `backend/app/models.py`, Pydantic schemas in `backend/app/schemas.py`, and a new router file `backend/app/routers/task_comments.py` registered in `backend/app/main.py`. The frontend should add typed API functions to `frontend/src/api/tasks.ts`, React Query hooks to `frontend/src/hooks/useTasks.ts`, TypeScript types to `frontend/src/types.ts`, and task-specific UI components under `frontend/src/components/tasks/` composed into `TaskModal.tsx`.

Keep comments independent from the task activity timeline for v1. The brief lists activity integration as nice-to-have, and the current `TaskActivityAction` enum only supports task creation, status changes, assignment changes, and field changes. Extending that enum would require a PostgreSQL enum migration and extra formatting work. A dedicated comments section in the modal satisfies the must-have scope with less migration risk.

## Proposed End-to-End Structure

```text
Frontend TaskModal
  └─ TaskCommentsPanel.tsx
      ├─ useTaskComments(task.id)
      ├─ useCreateTaskComment()
      ├─ useUpdateTaskComment()
      └─ useDeleteTaskComment()
          └─ frontend/src/api/tasks.ts
              └─ /api/tasks/{task_id}/comments[/{comment_id}]
                  └─ backend/app/routers/task_comments.py
                      ├─ ensure_task_access(..., viewer/member)
                      ├─ task_comments service helpers or local router helpers
                      └─ TaskComment ORM table
```

## Component Boundaries

| Component | Responsibility | Communicates With |
|---|---|---|
| `backend/app/models.py::TaskComment` | Persistent comment record: task, author, body, timestamps, edit/delete metadata | Alembic migration, schemas, router/service |
| `backend/app/schemas.py` comment schemas | Validate create/update payloads and serialize responses with author metadata | Router response models, frontend API contract |
| `backend/app/routers/task_comments.py` | HTTP endpoints, session auth, task/workspace permission checks, response shaping | `auth.py`, `models.py`, `schemas.py`, DB session |
| Optional `backend/app/services/task_comment_service.py` | Reusable comment permission helpers if route code grows | Router, models, errors/auth |
| `frontend/src/types.ts` comment types | Shared frontend contract for comment responses and mutation payloads | API module, hooks, UI components |
| `frontend/src/api/tasks.ts` comment functions | Thin HTTP wrappers; no UI or React Query logic | `api/client.ts`, hooks |
| `frontend/src/hooks/useTasks.ts` comment hooks | React Query keys, list query, create/update/delete mutations, invalidation | API module, UI components |
| `frontend/src/components/tasks/TaskCommentsPanel.tsx` | Comment list, composer, empty/loading/error states | Hooks, i18n, presentational child components |
| `frontend/src/components/tasks/TaskCommentItem.tsx` | Single comment display, inline edit/delete controls, edited badge | Hooks callbacks, i18n |
| `frontend/src/i18n/translations.ts` | English/Japanese labels, placeholders, errors, edited marker | Task comments UI |

## Backend API Shape

Use task subresource routes because existing code already exposes `/api/tasks/{task_id}/activity`, `/sources`, `/dependencies`, and `/assignee-recommendations`.

| Method | Path | Auth rule | Request | Response |
|---|---|---|---|---|
| `GET` | `/api/tasks/{task_id}/comments` | `ensure_task_access(..., min_role="viewer")` | none | `list[TaskCommentResponse]`, chronological oldest-first |
| `POST` | `/api/tasks/{task_id}/comments` | `ensure_task_access(..., min_role="member")` | `TaskCommentCreate` | `TaskCommentResponse`, `201` |
| `PUT` | `/api/tasks/{task_id}/comments/{comment_id}` | authenticated author only | `TaskCommentUpdate` | `TaskCommentResponse` |
| `DELETE` | `/api/tasks/{task_id}/comments/{comment_id}` | author, workspace admin/owner, org admin/owner, or workspace owner | none | `204 No Content` |

### Request/response schemas

Add these near the task schemas in `backend/app/schemas.py`:

```python
class TaskCommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=5000)


class TaskCommentUpdate(BaseModel):
    content: str = Field(min_length=1, max_length=5000)


class TaskCommentResponse(_BaseResponse):
    id: UUID
    task_id: UUID
    author_id: UUID
    author_email: Optional[str] = None
    content: str
    created_at: datetime
    updated_at: datetime
    edited_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
```

For v1, return only non-deleted comments from the list endpoint, so `deleted_at` is mostly future-proofing. The UI can distinguish edited comments via `edited_at != null` or `updated_at != created_at`; `edited_at` is clearer.

## Model Fields

Add a dedicated table instead of embedding comments in `tasks` JSON. A relational table supports ownership, task cascade delete, indexing by task/time, and future pagination.

Recommended ORM model in `backend/app/models.py`:

```python
class TaskComment(Base):
    __tablename__ = "task_comments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    edited_at = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_task_comments_task_created", "task_id", "created_at"),
        Index("ix_task_comments_author_id", "author_id"),
    )
```

### Field rationale

- `task_id`: task-scoped comments and `CASCADE` cleanup when a task is hard-deleted.
- `author_id`: must reference `users.id`, not `people.id`, because session auth returns a `User`; task activity currently uses `Person` for actor references, but comments are explicitly authored by authenticated users.
- `content`: plain text only; markdown/rich text is out of scope.
- `created_at` / `updated_at`: consistent with existing tables.
- `edited_at`: explicit UI signal for edited comments.
- `deleted_at`: optional soft-delete metadata; for v1, prefer hard delete or soft delete plus hidden list. Soft delete is safer for moderation/audit, but the UI should remove deleted comments from the visible thread.

## Router and Permission Design

Implement a new router rather than adding more routes to the already large `backend/app/routers/tasks.py` file. This mirrors `task_activity.py`, which uses the same `/api/tasks` prefix while isolating a task subdomain.

Recommended router skeleton:

```python
router = APIRouter(prefix="/api/tasks", tags=["task-comments"])
DbDep = Annotated[Session, Depends(get_db)]

@router.get("/{task_id}/comments", response_model=list[TaskCommentResponse])
def list_task_comments(task_id: UUID, db: DbDep, current_user: Annotated[User, Depends(get_current_user)]):
    ensure_task_access(task_id, current_user, db, min_role="viewer")
    ... order_by(TaskComment.created_at.asc(), TaskComment.id.asc())

@router.post("/{task_id}/comments", response_model=TaskCommentResponse, status_code=201)
def create_task_comment(...):
    ensure_task_access(task_id, current_user, db, min_role="member")
    ...

@router.put("/{task_id}/comments/{comment_id}", response_model=TaskCommentResponse)
def update_task_comment(...):
    ensure_task_access(task_id, current_user, db, min_role="viewer")
    comment = _get_comment_for_task(...)
    if comment.author_id != current_user.id: raise HTTPException(403, ...)
    ... set content, edited_at, commit

@router.delete("/{task_id}/comments/{comment_id}", status_code=204)
def delete_task_comment(...):
    task = ensure_task_access(task_id, current_user, db, min_role="viewer")
    comment = _get_comment_for_task(...)
    if comment.author_id != current_user.id:
        ensure_project_access(task.project_id, current_user, db, min_role="admin")  # see warning below
    ... delete or soft-delete, commit
```

Important permission warning: `ensure_project_access(..., min_role="admin")` will not work as written because `WORKSPACE_ROLE_PRIORITY` supports `owner`, `admin`, `manager`, `member`, and `viewer`, while project access delegates to workspace access. For admin/owner delete, call `ensure_task_access(..., min_role="admin")` or create a helper that checks whether the user is comment author or has workspace role at least `admin`. Existing org owner/admin access is already granted through `ensure_workspace_access`.

Use `HTTPException` in the router for consistency with `tasks.py` and `task_activity.py`, despite `.planning/codebase/CONVENTIONS.md` preferring error classes. Do not put FastAPI `HTTPException` in a service helper if a service file is added.

## Migration Strategy

Create a new Alembic revision after current head `014_memory_audit_events.py`, likely `015_task_comments.py`.

Upgrade should:

1. Create `task_comments` table with UUID primary key.
2. Add FK `task_id → tasks.id ON DELETE CASCADE`.
3. Add FK `author_id → users.id ON DELETE CASCADE`.
4. Add `content TEXT NOT NULL`.
5. Add timestamp columns with timezone and `server_default=sa.func.now()` for `created_at` and `updated_at`.
6. Add nullable `edited_at` and `deleted_at`.
7. Add indexes `ix_task_comments_task_created(task_id, created_at)` and `ix_task_comments_author_id(author_id)`.

Downgrade should drop indexes first, then drop the table. No enum change is needed if comments stay outside `TaskActivityAction`; this is the lowest-risk migration path.

## Frontend Data Flow

1. `TaskModal` opens with a task object.
2. `TaskCommentsPanel` receives `taskId={task.id}` and calls `useTaskComments(task.id)`.
3. `useTaskComments` runs React Query with key `[...TASK_COMMENTS_KEY, taskId]`, enabled only when `taskId` is truthy.
4. `frontend/src/api/tasks.ts` calls `GET /api/tasks/${taskId}/comments`.
5. Panel renders loading, error, empty, and list states.
6. User submits non-empty plain text.
7. `useCreateTaskComment` posts to `POST /comments`; on success invalidate `[...TASK_COMMENTS_KEY, taskId]`.
8. User edits own comment inline; `useUpdateTaskComment` invalidates the same key.
9. User deletes own/admin-deletable comment; `useDeleteTaskComment` invalidates the same key.

Do not implement optimistic UI in v1. The brief says “appears immediately,” which can be satisfied by invalidating/refetching after a successful mutation and clearing the composer on success. Optimistic mutations add rollback complexity and are explicitly nice-to-have.

## Frontend API and Hook Shape

Add types to `frontend/src/types.ts`:

```ts
export interface TaskComment {
  id: string;
  task_id: string;
  author_id: string;
  author_email: string | null;
  content: string;
  created_at: string;
  updated_at: string;
  edited_at: string | null;
  deleted_at: string | null;
}

export interface TaskCommentCreate { content: string; }
export interface TaskCommentUpdate { content: string; }
```

Add functions to `frontend/src/api/tasks.ts`:

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

Add hooks to `frontend/src/hooks/useTasks.ts`:

```ts
export const TASK_COMMENTS_KEY = ['task-comments'] as const;

export function useTaskComments(taskId: string | null) { ... staleTime: 30_000 }
export function useCreateTaskComment() { ... invalidate [...TASK_COMMENTS_KEY, taskId] }
export function useUpdateTaskComment() { ... invalidate [...TASK_COMMENTS_KEY, taskId] }
export function useDeleteTaskComment() { ... invalidate [...TASK_COMMENTS_KEY, taskId] }
```

## UI Composition

Add a comments section in `TaskModal.tsx` between task details/sources and the activity timeline, or immediately above activity so discussion and automated audit remain visually separate.

Recommended components:

- `TaskCommentsPanel.tsx`: owns query/mutation hooks, composer state, validation, and all states.
- `TaskCommentItem.tsx`: displays author email, formatted timestamp, content, edited badge, and edit/delete controls.

UI behavior:

- Chronological order oldest-first to read like a thread.
- Composer at bottom of the comments panel.
- Disable submit for empty/whitespace-only content.
- Show mutation pending states (`Posting…`, `Saving…`, `Deleting…`).
- Show edited label when `edited_at` exists.
- Show delete controls for all comments only if the backend allows it is impossible to know perfectly without role data in `TaskModal`; simplest v1 is to always attempt delete when visible for current user's comments and show server errors if forbidden. Better v1: compare `comment.author_id` to `currentUser.id` via `useAuth()` for author actions, and optionally omit admin delete affordance unless the current workspace role is readily available.

The existing `AuthContext` exposes the current user; if importing it into the comments component is straightforward, use it to hide edit/delete for non-authors. Backend remains authoritative regardless of UI visibility.

## Internationalization

Add matching `taskModal` keys in English and Japanese:

- `comments`
- `loadingComments`
- `noComments`
- `commentPlaceholder`
- `postComment`
- `postingComment`
- `editComment`
- `saveComment`
- `savingComment`
- `deleteComment`
- `deletingComment`
- `edited`
- `commentLoadError`
- `commentActionError`

Avoid hardcoded strings in `TaskCommentsPanel.tsx` and `TaskCommentItem.tsx`; this feature is explicitly required to work in all supported UI languages.

## Build Order

1. **Backend model + migration**
   - Add `TaskComment` to `models.py`.
   - Generate/create Alembic revision `015_task_comments.py`.
   - Verify upgrade/downgrade locally.

2. **Backend schemas + router**
   - Add `TaskCommentCreate`, `TaskCommentUpdate`, `TaskCommentResponse`.
   - Add `task_comments.py` with list/create/update/delete.
   - Register router in `main.py`.
   - Manually test endpoints with authenticated session or existing test harness.

3. **Backend permission edge cases**
   - Verify viewer can list but cannot create.
   - Verify member can create.
   - Verify author can edit/delete own comment.
   - Verify non-author member cannot edit/delete.
   - Verify workspace admin/owner can delete other comments.

4. **Frontend API/types/hooks**
   - Add types, API functions, query key, and mutations.
   - Confirm React Query invalidation causes new/edited/deleted comments to appear without page refresh.

5. **Frontend comments UI**
   - Add `TaskCommentsPanel` and `TaskCommentItem`.
   - Compose into `TaskModal`.
   - Handle loading, empty, error, edit, delete confirmation, and pending states.

6. **i18n + polish**
   - Add EN/JA strings.
   - Confirm modal scroll behavior remains usable with sources, comments, and activity sections.

7. **End-to-end manual verification**
   - Test with at least two users/roles if seed data allows.
   - Include browser demo evidence and PR checklist notes.

## Patterns to Follow

### Pattern: Task subresource router

**What:** A separate router file can share `prefix="/api/tasks"` for subresources.  
**Why:** `task_activity.py` already does this for `/api/tasks/{task_id}/activity`, keeping `tasks.py` from growing further.  
**Apply:** Use `task_comments.py` with tag `task-comments` and register in `main.py` next to `task_activity`.

### Pattern: Server-enforced permissions through `auth.py`

**What:** Routes call `get_current_user` and `ensure_task_access`.  
**Why:** The assignment explicitly rejects UI-only permissions.  
**Apply:** Every comment route must call `ensure_task_access`; edit/delete must also check authorship or admin role.

### Pattern: React Query hooks own cache behavior

**What:** API modules are thin; hooks define query keys and invalidation.  
**Why:** Existing `useTasks.ts` follows this pattern for tasks, activity, sources, and recommendations.  
**Apply:** Add `TASK_COMMENTS_KEY` and invalidation in comment mutation `onSuccess` callbacks.

## Anti-Patterns to Avoid

### Anti-Pattern: Embedding comments in the task response

**Why bad:** It bloats every task fetch, complicates permissions and ordering, and couples task CRUD to comment thread state.  
**Instead:** Fetch comments only when `TaskModal` opens via `/api/tasks/{task_id}/comments`.

### Anti-Pattern: Reusing `TaskActivityEvent` for comments in v1

**Why bad:** It needs enum expansion, activity formatting changes, and may confuse human discussion with automated audit logs.  
**Instead:** Add a dedicated `task_comments` table and leave activity integration as a documented stretch.

### Anti-Pattern: Frontend-only author/admin checks

**Why bad:** A user can call endpoints directly.  
**Instead:** Backend must enforce author-only edit and author/admin/owner delete.

### Anti-Pattern: Markdown/rich text now

**Why bad:** Adds sanitization/XSS complexity and is out of scope.  
**Instead:** Store and render plain text. React escapes string content by default when rendered as text.

## Scalability Considerations

| Concern | At candidate-task scale | Later if comments grow |
|---|---|---|
| Comment count | Return all comments ordered by `created_at ASC` | Add cursor pagination using `(created_at, id)` |
| Query performance | `ix_task_comments_task_created` is enough | Add partial index for `deleted_at IS NULL` if soft deletes are used heavily |
| Realtime updates | React Query invalidation after mutations | Add polling, SSE, or websocket only if required |
| Moderation/audit | Soft-delete with `deleted_at` preserves metadata | Add `deleted_by_user_id` and activity/audit event integration |
| Notifications | Out of scope | Add comment-created event/webhook later |

## Open Questions / Validation Flags

- Confirm whether `AuthContext` exposes only user identity or also workspace role. If role is not available, do not overbuild admin delete visibility; rely on backend enforcement and show an error if forbidden.
- Confirm test fixture patterns before writing tests. The architecture is clear, but exact test utilities were not reviewed in this research pass.
- Decide hard delete vs soft delete before implementation. This recommendation leans soft delete because it supports moderation, but hard delete also satisfies the brief and is simpler.

## Sources

- `.planning/PROJECT.md` — validated feature scope, constraints, likely integration points.
- `candidate-task.md` — must-have behavior, nice-to-have exclusions, PR/demo expectations.
- `.planning/codebase/ARCHITECTURE.md` — layered backend and React Query/frontend boundaries.
- `.planning/codebase/STRUCTURE.md` — file locations and add-new-code guidance.
- `.planning/codebase/CONVENTIONS.md` — router, schema, hook, error, and naming conventions.
- `backend/app/routers/tasks.py` — existing task CRUD/subresource patterns and activity helper placement.
- `backend/app/routers/task_activity.py` — precedent for separate task subresource router under `/api/tasks`.
- `backend/app/models.py` — current ORM style, role enums, task/activity/source tables.
- `backend/app/schemas.py` — current Pydantic response/request patterns.
- `backend/app/auth.py` — session auth, task/project/workspace access helpers and role hierarchy.
- `frontend/src/api/tasks.ts`, `frontend/src/hooks/useTasks.ts`, `frontend/src/components/tasks/TaskModal.tsx`, `frontend/src/types.ts`, `frontend/src/i18n/translations.ts` — frontend integration patterns.
