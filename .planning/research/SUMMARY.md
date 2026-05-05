# Project Research Summary

**Project:** Task Comments Candidate Assignment  
**Domain:** Brownfield task/project management comment threads  
**Researched:** 2026-05-05  
**Confidence:** HIGH

## Executive Summary

Task Comments should be implemented as a small, first-party collaboration feature inside the existing AI Task Management Platform. The product need is straightforward: team members need an in-context, task-scoped discussion thread that complements automated activity logs without becoming a full collaboration or notification subsystem. Mature products such as Jira, GitHub Issues, Trello, and Asana all model comments as task/issue child resources with attribution, timestamps, CRUD operations, and permission checks; for this candidate assignment, the winning implementation is reliable plain-text CRUD with server-side authorization and native UI fit.

The recommended v1 approach is to use only the repository's existing stack: FastAPI routers, dependency-based session auth, SQLAlchemy ORM, Alembic migrations, PostgreSQL-compatible UUID/text/timestamp fields, React + TypeScript API wrappers, TanStack Query hooks, and existing English/Japanese i18n. Add a dedicated `TaskComment` table and nested `/api/tasks/{task_id}/comments` routes; do not embed comments in task payloads and do not reuse the task activity timeline as the comment source of truth.

The critical risks are authorization, migration safety, scope creep, and frontend state drift. Mitigate them by building backend model/migration and permission-tested API routes before UI polish, enforcing task/workspace access on every endpoint, using React Query invalidation instead of local-only state or optimistic updates, rendering plain text safely, and explicitly deferring markdown, mentions, realtime, notifications, pagination, and activity integration unless the core is complete and verified.

## Key Findings

### Recommended Stack

Use the existing application stack without adding runtime dependencies. The feature fits current codebase conventions: one new backend task subresource router, one new ORM model and Alembic migration, Pydantic request/response schemas, typed frontend API functions, React Query hooks, and an isolated task comments component rendered inside `TaskModal.tsx`.

**Core technologies:**
- FastAPI `APIRouter`: expose nested task comment routes under `/api/tasks` to match task activity/sources/dependencies patterns.
- Existing `get_current_user`, `ensure_task_access`, and workspace role helpers: enforce read/create/edit/delete rules on the server.
- SQLAlchemy ORM + Alembic: add a reversible `task_comments` schema migration with stable FKs and indexes.
- PostgreSQL-compatible UUID/Text/DateTime columns: store first-class task-scoped comments with server timestamps.
- Pydantic schemas: validate create/update payloads and serialize author/timestamp/edited metadata.
- React + TypeScript: add `TaskComment`, `TaskCommentCreate`, and `TaskCommentUpdate` frontend types.
- TanStack Query v5: fetch comments and invalidate the task-specific comments key after create/update/delete.
- Existing i18n translations: add English and Japanese strings; do not hard-code UI copy.

**Critical version/implementation requirements:**
- New migration should follow current Alembic head after `014_memory_audit_events`, likely `015_task_comments.py`.
- Use chronological ordering by `created_at ASC, id ASC` for deterministic thread order.
- Use a practical content max length such as 5,000 chars and reject trimmed empty/whitespace-only comments on the backend.
- Prefer plain-text storage/rendering for v1; React text rendering plus wrapping/`whitespace-pre-wrap` avoids HTML/XSS complexity.

### Expected Features

The candidate brief defines a deliberately small 2-3 day assignment. Missing core CRUD, permissions, i18n, or async states would make the implementation feel incomplete or unsafe.

**Must have (table stakes):**
- View comments on a task — users who can view a task can read its comments in the task detail/modal context.
- Chronological ordering — choose one order and enforce it in the backend; research recommends oldest-first.
- Add plain-text comment — workspace members can create comments and see the updated list after server success.
- Display author, timestamp, and content — API should return enough author display data without frontend global user lookups.
- Edit own comment — author-only edit with backend ownership enforcement.
- Edited indicator — expose `edited_at` or equivalent and show a localized edited label.
- Delete own comment — author can remove their own comment.
- Admin/owner moderation delete — workspace admin/owner can delete any comment in the workspace.
- Server-enforced permissions — frontend hiding is optional convenience, never the source of truth.
- Empty/loading/error states — required for native React Query UX.
- English/Japanese support — all labels, placeholders, states, errors, and confirmations need translations.
- Backend validation and safe rendering — reject empty/oversized content and render plain text only.

**Should have / best stretch:**
- Relative timestamps — lowest-risk optional polish if all table stakes are complete; keep absolute timestamp available if easy.

**Defer / stretch items:**
- Pagination/load-more — useful later for high-volume tasks, but adds API and query-key design.
- Activity timeline integration — product-relevant later, but v1 should avoid task activity enum migration and audit/log formatting changes.
- Optimistic UI — not needed; invalidation/refetch after successful mutation is reliable enough.
- Markdown/rich text — adds sanitizer/editor/security review; plain text satisfies v1.
- `@mention` autocomplete — requires workspace member search, parsing, notification expectations, and permission edge cases.
- Comment counts/badges, soft-delete tombstones, edit history, reactions, notifications, webhooks, global search, AI summaries, and realtime updates — all v2+ collaboration layers.

### Architecture Approach

Add comments as a first-class task child resource with a narrow end-to-end path: `TaskModal` renders a focused `TaskComments`/`TaskCommentsPanel` component, which uses React Query hooks in `frontend/src/hooks/useTasks.ts`, which call thin API wrappers in `frontend/src/api/tasks.ts`, which hit a new `backend/app/routers/task_comments.py` router backed by a `TaskComment` ORM model. Keep comments visually near task detail/activity but architecturally separate from automated task activity events.

**Major components:**
1. `backend/app/models.py::TaskComment` — persistent comment record with task FK, author FK, content, timestamps, edited marker, and indexes.
2. `backend/alembic/versions/015_task_comments.py` — reversible schema creation with FK behavior and index teardown on downgrade.
3. `backend/app/schemas.py` — `TaskCommentCreate`, `TaskCommentUpdate`, and `TaskCommentResponse` contracts.
4. `backend/app/routers/task_comments.py` — list/create/update/delete endpoints, auth dependencies, task/workspace access, authorship/admin checks, response shaping.
5. `backend/app/main.py` — router registration under the existing API app.
6. `frontend/src/types.ts` — shared TypeScript comment contracts.
7. `frontend/src/api/tasks.ts` — thin comment HTTP functions with no UI logic.
8. `frontend/src/hooks/useTasks.ts` — `TASK_COMMENTS_KEY`, list query, and mutation hooks with invalidation.
9. `frontend/src/components/tasks/TaskComments.tsx` or `TaskCommentsPanel.tsx` — comment list, composer, edit/delete UI, and loading/empty/error states.
10. `frontend/src/components/tasks/TaskModal.tsx` — composition point for the comments section, without broad modal refactors.
11. `frontend/src/i18n/translations.ts` — English/Japanese strings for all comment UI states and actions.

**Key patterns to follow:**
- Use a separate task subresource router with `prefix="/api/tasks"`, mirroring `task_activity.py`.
- Call `ensure_task_access` on every route; mutate routes add authorship and workspace admin/owner checks.
- Validate `comment_id` belongs to the path `task_id` to avoid cross-task/cross-workspace access leaks.
- Keep API functions thin and put query keys/invalidation in hooks.
- Isolate UI state in a child component rather than expanding `TaskModal.tsx` with unrelated form state.

### Critical Pitfalls

1. **UI-only permission checks** — backend must enforce task visibility, workspace membership, authorship, and admin/owner delete; add direct API tests or manual checks for forbidden users.
2. **Weak data model or missing auth path** — use a dedicated `TaskComment` table with task FK and author FK; always authorize through task -> project -> workspace.
3. **Unsafe Alembic migration** — create a reversible migration, match model/schema columns, drop indexes before table on downgrade, and update any explicit test table setup.
4. **Treating comments as activity logs** — do not use `TaskActivityEvent` as source of truth; defer activity integration to avoid enum and UI formatting risk.
5. **Scope creep** — mentions, markdown, realtime, pagination, optimistic UI, notifications, and webhooks can consume the 2-3 day budget and destabilize must-haves.
6. **Frontend state drift** — use typed API wrappers and React Query invalidation after mutations; avoid component-local server state as the primary source of truth.
7. **Missing i18n and weak content handling** — add EN/JA strings and backend validation; render comment content as text, not HTML/markdown.

## Recommended v1 Scope

Build exactly this for v1:

- Dedicated `TaskComment` model and reversible Alembic migration.
- Nested REST endpoints: `GET /api/tasks/{task_id}/comments`, `POST /api/tasks/{task_id}/comments`, `PUT /api/tasks/{task_id}/comments/{comment_id}`, `DELETE /api/tasks/{task_id}/comments/{comment_id}`.
- Permission rules: viewers can list; workspace members can create; authors can edit/delete own; workspace admin/owner can delete any; all enforced server-side.
- Plain-text content with backend trim/empty/max-length validation and safe text rendering.
- Author/timestamp/content display, chronological order, and explicit edited marker.
- React Query hooks with invalidation after create/update/delete.
- Task modal comments component with loading, empty, error, pending, edit, delete confirmation, and disabled submit states.
- English and Japanese translation keys.
- Targeted backend permission/validation tests if practical, plus concrete manual browser QA and PR notes.

Do not include in v1 unless all above is complete and verified: pagination, mentions, markdown/rich text, activity timeline events, optimistic UI, realtime updates, notifications, webhooks, reactions, global comment search, AI summaries, or comment count badges. Relative timestamps are the only recommended stretch.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 0: Workflow Setup and Scope Guardrails
**Rationale:** The brief evaluates branch discipline, commits, PR hygiene, and scope control as much as the feature. Guardrails prevent over-building before core risks are solved.  
**Delivers:** Feature branch, confirmed v1/deferred scope, implementation assumptions, and commit/PR checklist.  
**Addresses:** Candidate workflow requirements; explicit decision to prioritize must-haves.  
**Avoids:** Working on `main`, one giant commit, AI disclosure omissions, and early stretch work.

### Phase 1: Data Model and Migration
**Rationale:** Comments need a first-class persistence model before permissions, API responses, and UI can be implemented safely.  
**Delivers:** `TaskComment` ORM model, indexes, reversible Alembic migration, and any test metadata updates.  
**Addresses:** Task-scoped comment storage, author identity, timestamps, edited marker, cascade/delete behavior.  
**Avoids:** Weak authorization paths, embedded task JSON, irreversible migrations, and activity-log-as-comments design.

### Phase 2: Backend API, Authorization, and Validation
**Rationale:** Authorization is the highest-risk acceptance criterion and should be proven before frontend work can mask backend gaps.  
**Delivers:** CRUD router, Pydantic schemas, task/workspace access checks, authorship/admin delete checks, trim/max-length validation, deterministic ordering, and focused tests/manual endpoint checks.  
**Addresses:** View, create, edit own, delete own, admin/owner delete any, server-enforced permissions, safe input.  
**Avoids:** UI-only security, cross-workspace leaks, whitespace-only comments, incorrect author/timestamp responses, and single-user happy-path testing.

### Phase 3: Frontend Data Layer and Task Modal UI
**Rationale:** Once API contracts are stable, the frontend can follow existing typed API + React Query patterns without local state drift.  
**Delivers:** TypeScript comment types, API wrappers, React Query hooks/query key, isolated comments component, TaskModal integration, list/composer/edit/delete states.  
**Addresses:** Native UI fit, immediate post/edit/delete visibility through invalidation, author/timestamp/content display, edited indicator, empty/loading/error states.  
**Avoids:** Direct fetches in components, broad `TaskModal` refactors, stale UI after mutations, optimistic rollback complexity.

### Phase 4: i18n, Polish, and Verification
**Rationale:** i18n and end-to-end usability are explicit acceptance criteria, and frontend automated tests may be limited.  
**Delivers:** English/Japanese strings, validation/error microcopy, delete confirmation, layout/scroll cleanup, TypeScript/build/lint/backend test runs where available, and manual browser QA across roles/languages.  
**Addresses:** All supported UI languages, async/error states, no console errors, reproducible demo evidence.  
**Avoids:** Hardcoded English, vague manual QA, broken modal layout, debug logs, and reviewer uncertainty.

### Phase 5: PR Packaging and Stretch Decision
**Rationale:** The final submission must communicate what was built, what was skipped, how to test it, and how AI was used. Stretch should only happen after must-haves are demonstrably complete.  
**Delivers:** PR description with checklist, skipped/deferred items, future improvements, local commands, click path, screenshots/video, and clear commit story. Optionally add relative timestamps only if safe.  
**Addresses:** Candidate engineering hygiene and honest communication requirements.  
**Avoids:** Missing demo link, undisclosed skipped items, unreadable commit history, and accidental partial stretch features.

### Phase Ordering Rationale

- Data model must precede API; API permission behavior must precede UI because frontend controls cannot be trusted for access control.
- Frontend data hooks should wait for stable response shapes and route semantics to avoid churn in types and query invalidation.
- i18n and QA are not optional cleanup; they should close the implementation after functional UI is integrated.
- PR packaging is a real phase because the candidate brief explicitly evaluates communication, reproducibility, demo evidence, and commit history.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 1:** Confirm exact current Alembic head, UUID/timestamp conventions, and whether tests maintain explicit table lists.
- **Phase 2:** Inspect exact `ensure_task_access` return shape, workspace role helper behavior, DirectClient/test fixture patterns, and not-found vs forbidden conventions.
- **Phase 3:** Confirm `AuthContext` exposes current user and whether workspace role is available for admin delete affordance; inspect existing modal layout constraints.

Phases with standard patterns (skip research-phase unless implementation uncovers surprises):
- **Phase 0:** Candidate workflow and scope are fully specified by `candidate-task.md` and `.planning/PROJECT.md`.
- **Phase 4:** i18n and QA checklist are repository/brief-driven; no external research needed.
- **Phase 5:** PR checklist and stretch/defer messaging are directly specified by the brief.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Repository fit is clear: existing FastAPI, SQLAlchemy, Alembic, React Query, typed API, and i18n patterns cover v1 without dependencies. Exact line placement still needs code inspection during implementation. |
| Features | HIGH | Candidate brief and project context directly define must-haves and out-of-scope/stretch items; competitor docs support but are not required to justify scope. |
| Architecture | HIGH | Existing task subresource patterns, frontend API/hook boundaries, and TaskModal integration points are well documented. Some exact helper signatures need validation. |
| Pitfalls | HIGH | Risks map directly to explicit evaluation criteria: server permissions, reversible migrations, i18n, QA, and PR hygiene. |

**Overall confidence:** HIGH

### Gaps to Address

- **Hard delete vs soft delete:** Research is split; for candidate v1, prefer hard delete unless existing product conventions favor soft delete. Decide in Phase 1 before migration.
- **Author display source:** Prefer `author_email_snapshot` or API-provided author email to avoid frontend user lookup; confirm current `User` fields during implementation.
- **Admin delete UI visibility:** If workspace role is not readily available in frontend context, do not add a new permissions API; either show author-only controls or rely on backend rejection for attempted admin actions.
- **Test harness details:** Confirm backend test fixtures, SQLite metadata setup, and DirectClient route dispatch before committing to automated test scope.
- **Exact auth helper semantics:** Validate `ensure_task_access(..., min_role="admin")` and org owner/admin behavior before implementing moderation delete.

## Sources

### Primary (HIGH confidence)
- `candidate-task.md` — must-have scope, nice-to-have/stretch list, working agreement, completion checklist, and evaluation priorities.
- `.planning/PROJECT.md` — active requirements, repository constraints, integration points, and out-of-scope decisions.
- `.planning/research/STACK.md` — recommended technologies, dependency decisions, backend/frontend file changes, validation checklist.
- `.planning/research/FEATURES.md` — table stakes, differentiators, anti-features, MVP recommendation, acceptance notes.
- `.planning/research/ARCHITECTURE.md` — component boundaries, API shape, model fields, frontend data flow, build order, patterns/anti-patterns.
- `.planning/research/PITFALLS.md` — critical/moderate/minor pitfalls, prevention strategies, phase-specific warnings.
- `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/STRUCTURE.md`, `.planning/codebase/CONVENTIONS.md`, `.planning/codebase/TESTING.md`, `.planning/codebase/CONCERNS.md` — repository conventions and known implementation risks as cited by research files.

### Secondary (MEDIUM-HIGH confidence)
- FastAPI official docs / Context7 `/fastapi/fastapi` — APIRouter, `response_model`, and status code patterns.
- SQLAlchemy ORM docs / Context7 `/websites/sqlalchemy_en_20_orm` — FK cascade, relationships, ordering, indexes.
- TanStack Query docs / Context7 `/tanstack/query` — mutation `onSuccess` and `queryClient.invalidateQueries({ queryKey })` refresh pattern.
- Jira Cloud REST issue comments — official comment CRUD, timestamps/authors, ordering/pagination, and permission gates.
- GitHub REST issue comments — official issue comment CRUD, chronological/paginated lists, markdown-rich mature feature evidence.

### Secondary (MEDIUM confidence)
- Trello REST actions API — comments as card actions and reactions; useful for stretch ranking.
- Asana stories API — task comments/stories as task-related discussion/activity primitive; retrieved partially.

---
*Research completed: 2026-05-05*  
*Ready for roadmap: yes*
