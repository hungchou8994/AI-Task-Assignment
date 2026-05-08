# Domain Pitfalls: Task Comments

**Domain:** Brownfield task comments in an AI task/project management platform  
**Researched:** 2026-05-05  
**Scope:** Authorization, data modeling, frontend state, i18n, migrations, testing, and candidate-assignment PR expectations.

## Critical Pitfalls

Mistakes that can cause security failures, rejected PRs, or major rewrites.

### Pitfall 1: Enforcing comment permissions only in the UI

**What goes wrong:** The UI hides edit/delete buttons, but API routes still allow direct calls against comments the user should not control. This directly violates the brief's requirement that permissions are server-enforced.  
**Why it happens:** Developers add conditional rendering first and forget that hidden controls are not access control. Brownfield code already has known ownership-scope concerns around `Person`, so adding another weakly scoped resource would compound a known risk.  
**Consequences:** Any authenticated user who discovers a comment UUID may edit/delete another user's comment or read comments from a workspace they cannot access. Reviewers are likely to reject the feature even if the browser demo looks correct.  
**Warning signs:**
- Routes accept `comment_id` but never load the parent task/project/workspace before authorizing.
- Delete/edit route checks only `current_user` exists.
- Tests only assert buttons are hidden, not that forbidden HTTP requests return 403/404.
- Frontend conditionals contain more role logic than the backend.
**Prevention strategy:**
- Add backend guard helpers for: task visibility, workspace membership, comment authorship, and admin/owner override deletion.
- For every mutate route, fetch the comment joined through task -> project -> workspace and check the current user's workspace membership before applying author/admin rules.
- Return 404 for missing resources and 403 for real access denial following existing error conventions.
- Add backend tests for cross-user/cross-workspace read, edit, and delete denial, even if the existing test harness needs extra user/workspace setup.
**Phase should address:** Phase 2 — API and authorization, before frontend integration.

### Pitfall 2: Modeling comments without a workspace/task authorization path

**What goes wrong:** A `TaskComment` model stores `task_id`, `author_id`, content, and timestamps, but routes cannot efficiently prove workspace membership or admin/owner rights.  
**Why it happens:** The obvious minimal model is not enough for multi-tenant checks unless every endpoint follows the task -> project -> workspace path consistently.  
**Consequences:** Authorization becomes duplicated, slow, or incomplete. Later fixes may require data migration or route rewrites.  
**Warning signs:**
- `TaskComment` has no FK to `Task`, no `author_id`, or lacks clear cascade/delete behavior.
- API returns comments by task ID without first checking task visibility.
- Comment response schema omits fields needed by UI permission checks, such as `author_id`, `created_at`, `updated_at`, and/or edited marker.
- Routes query comments directly by ID and never validate the parent task's workspace.
**Prevention strategy:**
- Use a dedicated `TaskComment` table with `id`, `task_id`, `author_id`, `content`, `created_at`, `updated_at`, and optionally `deleted_at` only if soft delete is intentionally chosen.
- Keep v1 plain text; do not add markdown/rich text columns or mention metadata in the must-have implementation.
- Decide hard delete vs soft delete early. Prefer hard delete for the candidate v1 unless the product already uses soft delete elsewhere, because the brief only requires deletion, not audit retention.
- Ensure indexes on `task_id` and chronological ordering fields.
**Phase should address:** Phase 1 — database model, schema, and migration.

### Pitfall 3: Creating an irreversible or unsafe Alembic migration

**What goes wrong:** The migration works locally once but cannot be downgraded, fails against PostgreSQL, or diverges from SQLite-based tests.  
**Why it happens:** Backend tests run on in-memory SQLite while production uses PostgreSQL; migrations are easy to hand-edit incorrectly when adding FK/UUID/timestamp columns. The assignment explicitly requires reversible database changes.  
**Consequences:** PR fails engineering hygiene, reviewers cannot trust deployment safety, and future candidates inherit broken schema state.  
**Warning signs:**
- `downgrade()` is empty or only contains `pass`.
- Migration uses PostgreSQL-only syntax without considering the app's test metadata patching.
- New table is not included in test table setup if tests use explicit table lists.
- FK constraints have unclear `ondelete` behavior.
**Prevention strategy:**
- Generate and review a dedicated Alembic migration for `task_comments`.
- Implement a real downgrade that drops indexes/table in reverse order.
- Confirm SQLAlchemy model metadata, Pydantic schemas, and migration columns match exactly.
- Update backend test helpers if they maintain an explicit `ALL_TEST_TABLES` list.
- Run both targeted task/comment tests and the full backend pytest suite.
**Phase should address:** Phase 1 — migration and test harness alignment.

### Pitfall 4: Treating comments like activity logs instead of user-authored discussion

**What goes wrong:** Comments are shoehorned into the existing automated task activity timeline, making edit/delete semantics, author permissions, and content display awkward.  
**Why it happens:** The product already has activity tracking, so it is tempting to reuse it for comments. However, the brief distinguishes human discussion from automated activity and lists activity timeline integration as optional stretch.  
**Consequences:** Must-have work slows down, audit-log assumptions leak into UI, and core operations become harder to reason about.  
**Warning signs:**
- Comment creation writes only an activity event and no first-class comment row.
- Editing/deleting comments requires mutating historical audit events.
- UI cannot show a stable comment thread independent of activity log noise.
- Stretch activity integration appears before basic CRUD is complete.
**Prevention strategy:**
- Build comments as a first-class task child resource.
- Defer activity timeline integration unless all must-haves are complete and verified.
- If adding activity events later, emit them as secondary side effects without making them the source of truth.
**Phase should address:** Phase 0/1 — scope confirmation and data design.

### Pitfall 5: Over-scoping with mentions, markdown, real-time, pagination, or optimistic UI

**What goes wrong:** Nice-to-haves consume the 2-3 day budget and destabilize core CRUD/permissions.  
**Why it happens:** Comments seem simple, but each stretch item introduces hidden complexity: mention permissions, rich-text sanitization, real-time invalidation, pagination state, and optimistic rollback.  
**Consequences:** The PR looks ambitious but fails the evaluation priorities: working, safe, native, readable.  
**Warning signs:**
- Mentions, markdown, or optimistic cache writes appear before backend auth tests exist.
- Pagination is implemented before there is evidence of large comment volumes.
- WebSocket/SSE changes are introduced despite the brief saying React Query refresh/invalidation is enough.
- PR checklist has many partial items rather than completed must-haves.
**Prevention strategy:**
- Ship plain-text chronological comments first.
- Use React Query invalidation after create/edit/delete instead of optimistic updates for v1.
- Explicitly list skipped stretch items in the PR and explain that reliability and permission safety were prioritized.
**Phase should address:** Phase 0 — scope guardrails, reinforced during every phase review.

### Pitfall 6: Frontend state drift after create/edit/delete

**What goes wrong:** The UI posts successfully but the list does not refresh, edited badges disappear, stale comments remain after deletion, or errors leave forms in confusing states.  
**Why it happens:** Existing frontend convention uses typed API modules and TanStack Query invalidation. Deviating with local-only state in a task modal can easily create multiple sources of truth.  
**Consequences:** Demo fails in the browser even though API endpoints work. Users may double-post or believe actions failed.  
**Warning signs:**
- Comment list is stored only in component `useState` while mutations also hit the server.
- Query keys are inline literals in components instead of exported constants from a hook module.
- Mutations do not invalidate the specific task comments query.
- Loading, empty, and error states are missing despite being explicit checklist items.
**Prevention strategy:**
- Add a typed `frontend/src/api` module for comments or extend task API consistently.
- Add hooks such as `useTaskComments(taskId)`, `useCreateTaskComment`, `useUpdateTaskComment`, and `useDeleteTaskComment` with module-level query keys.
- Invalidate the task-specific comments query on mutation success; avoid optimistic UI unless added deliberately after baseline works.
- Handle disabled submit state, trimmed empty input, mutation errors, empty state, and loading skeleton/spinner.
**Phase should address:** Phase 3 — frontend data layer and component integration.

### Pitfall 7: Missing or inconsistent i18n strings

**What goes wrong:** Comment UI ships with English-only labels or hardcoded strings, breaking the requirement that the feature works in all supported UI languages.  
**Why it happens:** The existing translation file is large and fragile, so it is easy to add UI text directly in components to move faster.  
**Consequences:** Reviewers catch untranslated UI during demo or code review. Future translation maintenance gets harder.  
**Warning signs:**
- New component text includes literals like `Add comment`, `Edited`, `Delete`, `No comments yet`, or error messages directly in JSX.
- English keys are added but Japanese values are missing or copied in English.
- Translation keys are named inconsistently with existing task-domain keys.
**Prevention strategy:**
- Add all task-comment strings to `frontend/src/i18n/translations.ts` in both English and Japanese.
- Include empty/loading/error, edit/delete labels, edited marker, confirmation text if used, validation errors, and permission-related messages.
- During manual QA, switch languages and exercise list/create/edit/delete states.
**Phase should address:** Phase 3 — UI implementation, verified in Phase 4 QA.

### Pitfall 8: Weak validation and unsafe content rendering

**What goes wrong:** Empty comments, whitespace-only comments, extremely long payloads, or unsafe rendered content are accepted.  
**Why it happens:** Plain text feels low risk, but input boundaries still need to be defined on both API and UI. Rich-text/markdown stretch work can also introduce XSS if rendered unsafely.  
**Consequences:** Poor UX, database bloat, layout breakage, or security vulnerabilities if HTML/markdown rendering is introduced.  
**Warning signs:**
- Backend schema accepts `content: str` with no min/max length or trimming behavior.
- Frontend disables empty submit but backend still accepts whitespace via direct API calls.
- Code uses `dangerouslySetInnerHTML` or markdown rendering for v1.
- Very long unbroken content breaks the task modal layout.
**Prevention strategy:**
- Validate on the backend: trim or reject whitespace-only content and set a practical max length.
- Mirror validation in the frontend for UX but never rely on it for enforcement.
- Render comments as plain text, preserving line breaks only if done safely through normal text rendering/CSS.
- Add CSS wrapping for long words/URLs.
**Phase should address:** Phase 2 — API validation, Phase 3 — UI rendering.

### Pitfall 9: Author identity and timestamp ambiguity

**What goes wrong:** Comments show the wrong author, no author, server/client timestamp mismatch, or edited status is unclear.  
**Why it happens:** The app has users, people, workspace members, and assignees. Comments should be authored by authenticated users, not the globally scoped `Person` model with known tenant concerns.  
**Consequences:** Users cannot trust who said what; edit badges may be wrong; future audit/activity integration becomes harder.  
**Warning signs:**
- `author_id` points to `Person` instead of authenticated `User` without a clear reason.
- UI calculates edited status only locally or compares timestamps imprecisely.
- API omits author display fields and forces frontend to infer from unrelated lists.
- Timestamps are generated by the client instead of the server.
**Prevention strategy:**
- Use authenticated `User.id` as comment author.
- Store server-side `created_at` and `updated_at`; mark as edited when `updated_at > created_at` or expose an explicit `is_edited` response field.
- Return enough author display data for the UI to render without additional global `people` lookups.
- Avoid relying on the known globally readable `Person` endpoints for comment author display.
**Phase should address:** Phase 1 — model/schema, Phase 2 — API responses.

### Pitfall 10: Inadequate backend tests for multi-user and role behavior

**What goes wrong:** Happy-path tests pass, but authorship/admin/owner permissions are unverified.  
**Why it happens:** Existing tests seed one user by default, and auth/session logic has no dedicated test file. Multi-user cases require additional setup.  
**Consequences:** The riskiest requirement remains unproven; reviewers may manually discover forbidden actions work.  
**Warning signs:**
- Tests create, list, edit, and delete comments using only the seeded default user.
- No tests cover workspace admin/owner deleting another author's comment.
- No tests cover a regular member failing to edit/delete someone else's comment.
- Test client direct dispatcher is not updated for new comment endpoints.
**Prevention strategy:**
- Add `test_task_comments.py` with focused cases for list, create, edit own, delete own, admin/owner delete any, non-author forbidden, non-member forbidden, and validation errors.
- Extend helper setup to create additional users/memberships as needed.
- Update `DirectClient` dispatch if tests use the custom HTTP-like client.
- Run targeted tests first, then full backend pytest.
**Phase should address:** Phase 2 — API test coverage before frontend work.

### Pitfall 11: Breaking native codebase conventions

**What goes wrong:** The feature works but feels bolted on: new route style, inline HTTP exceptions, component-local API calls, ad-hoc query keys, or inconsistent file naming.  
**Why it happens:** Candidate tasks often optimize for speed and copy generic AI-generated patterns rather than reading the existing code. The brief explicitly evaluates fit with the codebase.  
**Consequences:** Reviewers mark down maintainability even if functionality works. Future maintainers must support two styles.  
**Warning signs:**
- Fetch calls are written directly inside React components instead of typed API modules/hooks.
- Backend routes use different prefixes, async handlers without need, or raw error handling inconsistent with `app/errors.py`.
- New schemas are scattered in unexpected files without matching existing router/schema conventions.
- Commit introduces broad refactors unrelated to comments.
**Prevention strategy:**
- Follow current FastAPI router/service/schema patterns and React Query API/hook patterns.
- Keep the integration point narrow, likely the existing task detail modal/page.
- Avoid unrelated cleanup in this PR, especially large fragile components.
- Mention any deliberate deviation in the PR description.
**Phase should address:** All phases, with explicit review in Phase 4.

### Pitfall 12: Candidate PR hygiene failures despite working code

**What goes wrong:** Implementation is acceptable but submission fails assignment expectations: work on `main`, one giant commit, missing demo evidence, missing checklist, or undisclosed AI assistance.  
**Why it happens:** Engineers treat the brief as feature-only and ignore the working agreement. The assignment states branch, commits, PR description, demo, reproducibility, and AI disclosure are part of evaluation.  
**Consequences:** Candidate appears careless or unable to follow professional workflow. Reviewers cannot reproduce or evaluate the work efficiently.  
**Warning signs:**
- Branch is `main` or commit history is one large final commit.
- Commit messages are `wip`, `fix`, or unexplained bulk changes.
- No `Co-Authored-By` trailer where AI materially shaped code.
- PR lacks local test commands, click path, skipped items, future improvements, or video/demo link.
**Prevention strategy:**
- Create `feature/task-comments` before implementation.
- Commit in logical increments: model/migration, API/tests, frontend API/hooks, UI/i18n, QA/docs.
- Use clear imperative commit messages and AI co-author trailers when appropriate.
- Prepare PR text using the provided checklist and include demo evidence before marking complete.
**Phase should address:** Phase 0 — workflow setup, Phase 5 — PR packaging.

## Moderate Pitfalls

### Pitfall 13: Comment ordering inconsistency

**What goes wrong:** API returns newest-first, UI assumes oldest-first, or new comments appear in a different position after refresh.  
**Warning signs:** No explicit `ORDER BY`; tests assert only count, not order; UI reverses arrays manually.  
**Prevention strategy:** Pick one ordering, document it, enforce it in the backend query, and test it. The project decision currently favors chronological oldest-first.  
**Phase should address:** Phase 2 — list endpoint and tests.

### Pitfall 14: Modal/page integration causes regressions in task editing

**What goes wrong:** Adding comments to the task modal disrupts existing task CRUD, labels, dependencies, activity, or layout behavior.  
**Warning signs:** Large rewrites to `TaskModal.tsx`; unrelated task form state changes; comment form shares state names with task fields.  
**Prevention strategy:** Add a focused `TaskComments` child component with isolated state and props. Avoid broad task modal refactors unless necessary.  
**Phase should address:** Phase 3 — UI integration.

### Pitfall 15: Assuming frontend tests exist

**What goes wrong:** No automated frontend safety net catches broken component states, because the repo has no detected frontend test framework.  
**Warning signs:** PR claims frontend tests pass without actually having a frontend test runner; manual QA is vague.  
**Prevention strategy:** Rely on TypeScript, lint/build if available, and explicit manual browser verification for comment states. Do not invent a frontend test framework unless the timeline allows and it is clearly justified.  
**Phase should address:** Phase 4 — QA and verification.

### Pitfall 16: Error messages leak resource existence across workspaces

**What goes wrong:** Forbidden users can distinguish valid comment/task IDs from invalid IDs, aiding data probing.  
**Warning signs:** Cross-workspace access returns detailed messages like `Comment belongs to another workspace`.  
**Prevention strategy:** For resources outside the user's visible scope, prefer not-found semantics where consistent with existing auth patterns; reserve 403 for visible resources where the user lacks a specific action permission.  
**Phase should address:** Phase 2 — authorization semantics.

## Minor Pitfalls

### Pitfall 17: Leaving debug logs or console output

**What goes wrong:** Browser console or backend logs contain temporary debugging output.  
**Warning signs:** `console.log`, `print`, or broad exception dumps appear in the diff.  
**Prevention strategy:** Remove debug output before PR; use existing logger conventions only if meaningful.  
**Phase should address:** Phase 4 — cleanup.

### Pitfall 18: Poor empty/loading/error microcopy

**What goes wrong:** The UI technically handles states but feels unfinished or untranslated.  
**Warning signs:** Empty state says only `No data`; errors expose raw `500: ...` text; Japanese strings are missing.  
**Prevention strategy:** Add concise translated state text and keep raw errors out of user-facing copy where possible.  
**Phase should address:** Phase 3 — UI/i18n, Phase 4 — QA.

### Pitfall 19: Not documenting skipped stretch items

**What goes wrong:** Reviewers wonder whether pagination, mentions, or optimistic UI were forgotten.  
**Warning signs:** PR checklist leaves stretch items blank without explanation.  
**Prevention strategy:** Mark stretch items not done and state they were intentionally deferred to prioritize reliable must-haves.  
**Phase should address:** Phase 5 — PR packaging.

## Phase-Specific Warnings

| Phase | Likely Pitfall | Mitigation |
|-------|----------------|------------|
| Phase 0: Setup and scope | Starting on `main`, adding stretch features early, skipping codebase reading | Create feature branch; restate must-haves; map existing task/auth/i18n patterns before coding |
| Phase 1: Model and migration | Weak model, missing downgrade, missing test metadata | Add first-class `TaskComment`; reversible Alembic migration; update test table setup |
| Phase 2: API and tests | UI-only auth, single-user happy-path tests, validation gaps | Implement server guards and multi-user/role tests before frontend |
| Phase 3: Frontend and i18n | Local state drift, hardcoded English, broad modal refactor | Use typed API + React Query hooks; add all translation keys; isolate comment component |
| Phase 4: QA and cleanup | Assuming compile means done, missing manual browser checks | Verify list/create/edit/delete, permissions, language switch, loading/empty/error, console clean |
| Phase 5: PR packaging | Missing checklist, demo, AI disclosure, or readable commit story | Prepare PR with checklist, skipped items, test commands, click path, demo/video, clear commits |

## Roadmap Implications

1. **Start with data and authorization, not UI polish.** The critical risk is unsafe access, so comments need a first-class model and server-side permission tests before visual integration.
2. **Keep v1 deliberately small.** Plain-text comments with React Query invalidation satisfy the brief and avoid markdown, mentions, optimistic rollback, and real-time complexity.
3. **Treat i18n and PR hygiene as must-haves.** They are explicit evaluation items, not cleanup tasks.
4. **Make manual QA concrete.** Because frontend tests are absent, the PR must include reproducible local commands, click path, and demo evidence.

## Sources

- `.planning/PROJECT.md` — project requirements, constraints, decisions, and intended integration points.
- `candidate-task.md` — assignment scope, working agreement, completion checklist, and evaluation priorities.
- `.planning/codebase/CONCERNS.md` — known security, performance, testing, and fragile-area concerns.
- `.planning/codebase/TESTING.md` — backend pytest patterns, DirectClient, SQLite test setup, and frontend test gap.
- `.planning/codebase/CONVENTIONS.md` — backend/frontend conventions and anti-patterns to follow/avoid.
