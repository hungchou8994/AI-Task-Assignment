# Feature Landscape: Task Comments

**Domain:** Task/project management comment threads  
**Project:** Task Comments Candidate Assignment  
**Researched:** 2026-05-05  
**Overall confidence:** HIGH for candidate scope; MEDIUM for broader ecosystem stretch ranking

## Scope Recommendation

Build a plain-text, per-task comment thread that is reliable, permission-safe, localized, and visually native to the existing task detail experience. The candidate brief is intentionally a 2-3 day brownfield assignment; therefore the roadmap should treat comment CRUD, author/timestamp display, edit indication, server authorization, and basic async states as the acceptance baseline.

Do **not** try to turn this into a full collaboration subsystem. Competitive systems such as Jira, GitHub Issues, Trello, and Asana all expose richer comment ecosystems over time--pagination, markdown/rich text, activity integration, mentions, reactions, visibility rules, notifications, and real-time updates--but those are separate product layers. For this assignment, shipping a small secure thread beats shipping broad but brittle collaboration features.

## Table Stakes

Features users and reviewers should expect. Missing any of these makes the assignment feel incomplete or unsafe.

| Feature | Why Expected | Complexity | Dependencies | Recommendation |
|---------|--------------|------------|--------------|----------------|
| View comments on a task | The core value is in-context discussion; Jira, GitHub Issues, and Asana all model comments/stories as child records of a task/issue. | Medium | Task detail UI, task ID routing/context, backend read endpoint, author joins | Must build. Show comments inside the existing task modal/detail area rather than a new top-level page. |
| Chronological ordering | Threads need stable reading order; GitHub issue comments are ordered ascending by default and Jira exposes ordering on comment lists. | Low | `created_at` field, deterministic query ordering | Must build. Use oldest-first unless existing activity UI strongly prefers newest-first; be consistent. |
| Add plain-text comment | Posting is the minimum collaboration action. | Medium | Authenticated user, workspace membership check, create endpoint, React Query mutation/invalidation | Must build. New comment should appear after successful server response; optimistic UI is not required. |
| Display author, timestamp, and content | The brief explicitly requires attribution and time context; all researched systems include creator and created/updated timestamps in comment payloads. | Low-Medium | User relationship, serialization schema, frontend display component | Must build. Prefer display name plus absolute/localized timestamp. |
| Edit own comment | Common permission pattern: Jira distinguishes edit own vs edit all; GitHub and Trello APIs expose update comment operations. | Medium | Comment ownership, update endpoint, edit UI state, validation | Must build. Inline edit or modal edit are both acceptable; keep UI simple. |
| Visually mark edited comments | Users need trust that content changed after original posting; Jira and GitHub payloads include updated timestamps/update authors. | Low | `updated_at` or `edited_at`, compare with `created_at` | Must build. A small localized "Edited" label is enough; no edit history needed. |
| Delete own comment | Baseline moderation and cleanup behavior; Jira, GitHub, and Trello all expose delete operations for comments/comment actions. | Medium | Ownership check, delete endpoint, confirmation affordance, cache invalidation | Must build. Hard delete is acceptable unless existing app has a soft-delete convention. |
| Admin/owner delete any workspace comment | Brief explicitly requires workspace moderation for inappropriate content. | Medium | Workspace role lookup, comment-to-task-to-workspace scope validation | Must build. Enforce on backend even if frontend hides controls. |
| Server-enforced permissions | Evaluation prioritizes safety; Jira's comment endpoints document browse/add/edit/delete permission checks, illustrating that authorization belongs at API boundary. | High | Existing auth guards, workspace/task access functions, tests or manual verification | Must build. Treat this as the highest-risk feature dependency. |
| Empty, loading, and error states | The candidate checklist requires them and they are essential for native UX with React Query. | Low | Comment query hook, localized strings | Must build. Empty state should invite first comment; errors should not crash task modal. |
| All supported UI languages | Existing app supports English/Japanese translations and the brief requires parity. | Low | `frontend/src/i18n/translations.ts` keys | Must build. Include all comment labels, buttons, confirmations, and error copy. |
| Input validation and safe rendering | Plain text still needs minimum validation and escaping to avoid empty spam and rendering issues. | Medium | Backend schema constraints, frontend form state | Must build. Reject empty/whitespace-only comments; consider a reasonable max length. Render as text, not raw HTML. |
| Native fit with existing architecture | Reviewers will evaluate codebase fit. | Medium | Existing FastAPI router/service/schema patterns, React Query hooks, shadcn/Radix UI | Must build. Add a comments API module/hook/component only where existing task code patterns suggest it. |

## Differentiators / Stretch

Useful extras only after all table-stakes behavior is complete, manually verified end-to-end, localized, and permission-safe.

| Feature | Value Proposition | Complexity | Dependencies | Candidate Recommendation |
|---------|-------------------|------------|--------------|--------------------------|
| Relative timestamps | Makes comments feel modern and scannable; brief lists it as nice-to-have. | Low | Date formatting utility, re-render interval or static relative labels, i18n | Best stretch if time remains. Keep absolute timestamp in tooltip/title if easy. |
| Pagination / load more | Jira and GitHub expose paginated comment APIs; needed when tasks have many comments. | Medium | Backend `limit/offset` or cursor, UI load-more, query key design | Optional stretch only. Defer for v1 unless API design can include default limits without UI complexity. |
| Activity timeline integration | Connects human comments with existing automated activity history, useful in this AI task platform. | Medium-High | Existing `task_activity` router/service/model semantics, event creation on comment create/update/delete | Good product stretch but risky for candidate scope. Defer unless core is finished early and existing activity pattern is trivial. |
| Optimistic UI | New comments feel instant and align with modern collaboration UX. | Medium | React Query optimistic mutations, rollback handling, temporary IDs | Optional stretch only. Safer to invalidate/refetch after server success for assignment reliability. |
| Markdown/basic rich text | GitHub and Jira support rich/structured comment bodies; improves expressiveness. | High | Parser/sanitizer, preview/rendering, security review, i18n/editor UX | Defer. Plain text is explicitly sufficient for must-have scope. |
| `@mention` autocomplete | Common collaboration differentiator that can drive notifications later. | High | Workspace member search, autocomplete UI, mention token storage, notification semantics | Defer. It creates product expectations for notifications and identity resolution. |
| Comment count/badge on task list | Helps users discover active discussions without opening every task. | Medium | Aggregate count query or denormalized count, task list UI | Consider future phase, not candidate baseline. It touches list performance and task query shape. |
| Soft-delete tombstone | Preserves conversational context after deletion. | Medium | `deleted_at`, `deleted_by`, display policy, moderation/audit decision | Future enhancement if audit requirements emerge. Hard delete is acceptable for candidate assignment. |
| Edit history/version history | Supports auditability and trust. | High | Comment revision table, UI to inspect versions, retention policy | Defer. Edited label satisfies current requirement. |
| Reactions | Trello and GitHub expose reactions; useful for lightweight acknowledgement. | Medium | Reaction model, per-user uniqueness, UI icons | Defer. Nice collaboration polish but unrelated to core discussion. |

## Anti-Features / Explicitly Deferred

Features that should be called out as intentionally not built in the candidate PR unless the brief changes.

| Anti-Feature / Deferred Item | Why Avoid Now | What to Do Instead |
|------------------------------|---------------|--------------------|
| Real-time cross-browser updates | Requires polling/SSE/WebSocket decisions and conflict handling; brief says React Query refresh/invalidation is enough for v1. | Refetch/invalidate comments after create/edit/delete; optional manual refresh by reopening task is acceptable if query invalidation works. |
| Notification delivery for comments | Mentions, subscriptions, email/in-app delivery, unread state, and rate limits form a separate notifications product. | Do not send notifications. Mention as future improvement. |
| Full markdown/rich editor | Adds sanitization and editor complexity; security bugs are more damaging than plain-text limitations. | Store/render plain text safely. Preserve line breaks if simple. |
| `@mention` autocomplete | Pulls in workspace member search, token parsing, and notification expectations. | Leave as future collaboration phase. |
| Nested replies/threaded sub-comments | Increases mental model and API complexity; not requested by brief or needed for task-level context. | Use a single flat task comment thread. |
| Comment visibility restrictions/private comments | Jira supports restricted visibility, but workspace/project scoped app permissions are already enough for this assignment. | Inherit task visibility: users who can view the task can view comments. |
| File attachments in comments | Requires upload/storage/security policy and UI previews. | Keep attachments out of scope; users can reference existing task/source context manually. |
| AI-generated comment summaries or suggested replies | Attractive for an AI platform but not in the candidate brief and can distract from collaboration basics. | Keep AI out of comment v1. Future phase may summarize long threads. |
| External integrations/webhooks for comments | Existing platform has webhooks, but adding comment events broadens API contracts and testing surface. | Defer unless activity integration becomes a later milestone. |
| Global comment search | Requires indexing/query UX and likely pagination. | Defer. Comments are accessed through their task. |
| Mobile/offline-first comment composition | Valuable in mature products but outside current browser candidate assignment. | Ensure responsive enough within existing UI only. |
| Perfect test coverage as a feature gate | Brief values working software and safety over 100% coverage. | Add targeted backend permission tests if practical; otherwise document manual verification clearly. |

## Feature Dependencies

```text
Task/workspace access checks -> list comments
Task/workspace access checks + workspace membership -> create comment
Comment model + author relationship -> display author/timestamp/content
Comment ownership check -> edit own comment
Comment ownership check + updated timestamp -> edited label
Comment ownership check OR workspace admin/owner role -> delete comment
Comment API module -> React Query hook -> TaskModal comment UI
i18n keys -> empty/loading/error/edit/delete/add UI
Core CRUD stability -> optional relative timestamps
Core CRUD stability -> optional pagination/load more
Core CRUD stability + activity event understanding -> optional activity timeline integration
Workspace member directory + notification policy -> future @mentions
Sanitization/rendering decision -> future markdown/rich text
```

## MVP Recommendation

Prioritize these in order:

1. **Data/API permission foundation**: comment model/migration, schemas, list/create/update/delete endpoints, and server-side task/workspace authorization.
2. **Native task detail UI**: comment list, form, edit/delete controls, empty/loading/error states, and React Query invalidation after mutations.
3. **Review polish**: edited label, localized English/Japanese strings, validation messages, confirmation for delete, and manual verification notes for normal member vs admin/owner behavior.

If there is genuine spare time after the above is demonstrably working, add **relative timestamps** only. It is the lowest-risk stretch from the brief and does not require new backend semantics.

Defer pagination, mentions, markdown/rich text, optimistic UI, activity timeline integration, and notifications. These are legitimate product features but not good candidate-assignment bets because they multiply edge cases across permissions, UX state, security, and data model design.

## Acceptance Notes for Roadmap

- A task comment should be an ordinary workspace-scoped child of a task, not a global chat message.
- Access should be inherited from task visibility: if a user can view the task, they can view comments.
- Create should require workspace membership in the task's workspace.
- Edit should be author-only for this assignment; admin edit-all is not required by the brief.
- Delete should allow author delete and workspace admin/owner moderation delete.
- The UI can hide unavailable controls, but every mutation endpoint must independently reject unauthorized users.
- Plain text is the safest v1 body format. Preserve user-entered line breaks if easy, but do not render arbitrary HTML.
- New comments should appear immediately after successful post via cache update or invalidation/refetch; do not take optimistic rollback risk unless all must-haves are complete.

## Sources

- Candidate brief, `candidate-task.md` (HIGH): defines must-have and nice-to-have scope, evaluation priorities, and 2-3 day constraint.
- Project context, `.planning/PROJECT.md` (HIGH): confirms brownfield constraints, existing stack conventions, and explicit out-of-scope items.
- Codebase structure, `.planning/codebase/STRUCTURE.md` (HIGH): identifies FastAPI, SQLAlchemy, Alembic, React Query, task modal, API modules, hooks, and i18n integration points.
- Jira Cloud REST API issue comments (HIGH): official docs show get/create/update/delete comment operations, pagination/order parameters, timestamps, authors/update authors, and permission gates for browse/add/edit/delete comments. https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-comments/
- GitHub REST API issue comments (HIGH): official docs show list/create/update/delete issue comments, ascending default order for issue comments, markdown body variants, timestamps, reactions, pinning, and pagination. https://docs.github.com/en/rest/issues/comments
- Trello REST API actions (MEDIUM-HIGH): official docs model card comments as comment actions that can be updated/deleted and can have reactions; useful evidence that reactions/activity integration are mature-product stretch, not baseline. https://developer.atlassian.com/cloud/trello/rest/api-group-actions/
- Asana Developers stories API (MEDIUM): official docs identify task stories/comments as a task-related discussion/activity primitive; page content was partially retrieved but enough to confirm comments are represented as task stories. https://developers.asana.com/reference/stories

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Candidate table stakes | HIGH | Directly specified by candidate brief and project context. |
| Stretch/defer ranking | HIGH | Brief explicitly labels most stretch items; ecosystem docs support that richer collaboration features are common but optional. |
| Competitor behavior | MEDIUM-HIGH | Jira/GitHub/Trello official docs verified; Asana fetch was partial. |
| Implementation complexity | MEDIUM | Based on mapped architecture, not full code inspection of specific auth/task functions. |
```
