# Frontend

## Overview

The frontend is a **React 19 + TypeScript** single-page application built with **Vite**. It uses **TanStack Query** for server state, **shadcn/ui** (Radix UI + Tailwind CSS) for the component system, and **React Router v7** for client-side routing.

## Tech Stack

| Library | Version | Purpose |
|---|---|---|
| React | ^19.0.0 | UI framework |
| TypeScript | ~5.8.2 | Type safety |
| Vite | ^6.2.0 | Build tool + dev server |
| React Router DOM | ^7.13.2 | Client-side routing |
| TanStack Query | ^5.90.21 | Server state + caching |
| Tailwind CSS | ^4.1.14 | Utility-first CSS |
| Radix UI | various | Headless UI primitives |
| shadcn/ui | — | Pre-built accessible components |
| Zod | ^4.3.6 | Runtime schema validation |
| React Hook Form | ^7.72.0 | Form state management |
| Recharts | ^3.8.0 | Data visualization charts |
| Lucide React | ^0.546.0 | Icon set |
| React Markdown | latest | Markdown rendering |
| date-fns | ^4.1.0 | Date formatting utilities |
| Sonner | ^2.0.7 | Toast notifications |

---

## Directory Structure

```
frontend/src/
├── main.tsx               # App entry: bootstraps React + all providers
├── routes.tsx             # Route definitions + auth guard
├── types.ts               # All TypeScript interfaces (single source of truth)
├── index.css              # Global styles (CSS variables, base resets)
│
├── pages/                 # Page-level components (route targets)
│   ├── AuthPage.tsx
│   ├── TaskDashboard.tsx
│   ├── TasksPage.tsx
│   ├── ReviewQueuePage.tsx
│   ├── AIAnalysisPage.tsx
│   ├── SourcesPage.tsx
│   ├── TeamMembersPage.tsx
│   ├── WebhooksSettingsPage.tsx
│   └── DocumentationPage.tsx
│
├── components/            # Reusable UI components
│   ├── ui/                # shadcn/ui primitives (Button, Dialog, Table, etc.)
│   ├── AgentLoopTimeline/ # Live agent event stream visualization
│   ├── TaskCard/
│   ├── ReviewCandidateCard/
│   └── ...
│
├── hooks/                 # ~20 TanStack Query data hooks
│   ├── useTasks.ts
│   ├── useTaskCandidates.ts
│   ├── usePeople.ts
│   ├── useWorkspaces.ts
│   ├── useProjects.ts
│   ├── useJobEventStream.ts   # SSE hook for agent event streaming
│   ├── useFeedbackAnalytics.ts
│   └── ...
│
├── api/                   # Typed API client functions
│   ├── client.ts          # Base HTTP client (GET/POST/PATCH/DELETE/postForm)
│   ├── auth.ts
│   ├── tasks.ts
│   ├── taskCandidates.ts
│   ├── ai.ts
│   ├── people.ts
│   ├── workspaces.ts
│   ├── webhooks.ts
│   ├── sources.ts
│   └── feedbackAnalytics.ts
│
├── context/               # React Contexts
│   ├── AuthContext.tsx
│   ├── WorkspaceContext.tsx
│   ├── ProjectContext.tsx
│   ├── ThemeContext.tsx
│   ├── SidebarContext.tsx
│   └── LanguageContext.tsx
│
├── i18n/                  # Internationalization
│   ├── en.ts              # English translations
│   └── ja.ts              # Japanese translations
│
├── lib/                   # Utilities
│   ├── api.ts             # Axios/fetch base config
│   ├── taskFormatters.ts  # Format task status/priority for display
│   └── decodeEscapedText.ts
│
└── constants/             # Shared constants
```

---

## Routing

All routes (except `/auth`) are workspace-scoped under `/:workspaceId/*` and protected by `ProtectedLayout` (redirects to `/auth` if not authenticated).

| Path | Page | Description |
|---|---|---|
| `/auth` | `AuthPage` | Login and registration forms |
| `/:workspaceId/dashboard` | `TaskDashboard` | Metrics overview: task counts, completion rates, charts |
| `/:workspaceId/tasks` | `TasksPage` | Task list with filters (status, priority, project, assignee, archived) |
| `/:workspaceId/review` | `ReviewQueuePage` | AI-generated task candidates pending human review |
| `/:workspaceId/ai` | `AIAnalysisPage` | Submit content for AI extraction + live agent event timeline |
| `/:workspaceId/sources` | `SourcesPage` | History of submitted source documents |
| `/:workspaceId/team` | `TeamMembersPage` | Team member profiles, skills, and availability |
| `/:workspaceId/settings/webhooks` | `WebhooksSettingsPage` | Manage webhook subscriptions |
| `/:workspaceId/documentation` | `DocumentationPage` | In-app platform documentation |

---

## Context Hierarchy

The provider tree wraps the entire app in this order:

```
BrowserRouter
  └── QueryClientProvider        (TanStack Query)
        └── ThemeProvider        (dark / light mode)
              └── SidebarProvider (sidebar collapsed state)
                    └── AuthProvider    (user session)
                          └── WorkspaceProvider  (workspace list + selection)
                                └── LanguageProvider  (i18n: en / ja)
                                      └── Routes
```

### `AuthContext`
- Stores the authenticated `User` object
- Exposes: `user`, `login()`, `register()`, `logout()`, `isLoading`
- Dispatches `auth:unauthorized` event on 401 responses (auto-logout)

### `WorkspaceContext`
- Stores the current workspace + list of accessible workspaces
- Exposes: `workspace`, `workspaces`, `setWorkspace()`
- Derives `workspaceId` from URL params

### `ProjectContext`
- Stores the currently selected project within a workspace
- Exposes: `project`, `projects`, `setProject()`

### `ThemeContext`
- Stores `"light"` or `"dark"` mode
- Persists to `localStorage`
- Applies Tailwind dark class to `<html>`

### `LanguageContext`
- Stores `"en"` or `"ja"`
- Auto-detects from `navigator.language` on first load
- Persists to `localStorage`
- Provides `t(key)` translation function

---

## API Layer

All API calls go through typed functions in `frontend/src/api/`. The base client (`api/client.ts`) handles:
- Credential inclusion (`credentials: "include"` for session cookies)
- Automatic `auth:unauthorized` event on 401 (triggers logout)
- JSON serialization/deserialization

Example: **submitting an extraction job**
```typescript
// api/ai.ts
export async function submitExtraction(payload: ExtractionRequest): Promise<{ job_id: string }> {
  return client.post("/api/ai/extract", payload);
}
```

Example: **streaming agent events**
```typescript
// hooks/useJobEventStream.ts
// Opens an EventSource SSE connection to GET /api/ai/jobs/{job_id}/events
// Appends events to local state as they arrive
// Automatically closes when "finalized" or "error" event is received
```

---

## Key Pages

### AIAnalysisPage
The most complex page. Flow:
1. User fills textarea with text / URL / email or selects content type
2. On submit: calls `submitExtraction()` → receives `job_id`
3. Opens SSE connection via `useJobEventStream(job_id)`
4. `AgentLoopTimeline` component renders each event in real-time:
   - Thinking deltas (reasoning tokens)
   - Tool calls with their arguments
   - Tool results
   - Final task list
5. On completion: shows extracted tasks with assignee recommendations

### ReviewQueuePage
- Lists all `pending` task candidates
- Each card shows: title, description, priority, due date, assignee recommendation with confidence score
- Actions: Approve, Reject, Edit (inline), Undo
- Batch approve/reject for bulk operations

### TaskDashboard
- Summary cards: total tasks, by status, by priority
- Completion rate over time (Recharts line/bar chart)
- AI accuracy metrics (approval rate, rejection rate)
- Recent task activity feed

### TasksPage
- Full task list with multi-filter sidebar (status, priority, project, assignee, labels, archived)
- Create / edit tasks via slide-over panel
- Inline status and priority updates

---

## Internationalization (i18n)

Translation files are in `frontend/src/i18n/`:
- `en.ts` — English (default)
- `ja.ts` — Japanese

The `t(key)` function is obtained from `useContext(LanguageContext)`. All UI strings use translation keys.

Language detection priority:
1. `localStorage.getItem("language")`
2. `navigator.language` (browser preference)
3. Fallback: `"en"`

---

## Building for Production

```bash
cd frontend
npm install
npm run build
# Output: frontend/dist/
```

The `dist/` folder is a static SPA. Configure your web server to serve `index.html` for all routes (SPA fallback).

For the Vite dev server with API proxy:
```bash
npm run dev
# Dev server on http://localhost:3000
# /api/* proxied to http://localhost:8000
```
