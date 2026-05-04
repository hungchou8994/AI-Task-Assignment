# Project Overview

## What is TGL AI Task Divider?

TGL AI Task Divider is an **AI-powered task management platform** that combines conventional project/task management with an intelligent intake pipeline. Its core value proposition is the ability to automatically extract actionable tasks from unstructured inputs — emails, meeting notes, plain text, or URLs — using large language models.

## The Core Loop

```
1. User submits unstructured content (email, meeting notes, URL)
        ↓
2. AI Agent analyzes content and extracts structured tasks
        ↓
3. Extracted tasks enter a Human Review Queue as "candidates"
        ↓
4. Human approves, edits, or rejects each candidate
        ↓
5. Approved candidates become real Tasks in the project
        ↓
6. Feedback analytics tracks AI accuracy over time
```

## Key Features

### Task Management
- Full CRUD for tasks with status, priority, due dates, and effort estimates
- Project and workspace hierarchy with multi-tenancy support
- Labels, task dependencies (blocks / relates_to), and task activity logs
- Status transition history and field change audit trail
- Archive/unarchive tasks

### AI Extraction Pipeline
- Accepts raw text, URLs, or emails as input
- An autonomous agent loop (think → act → observe) extracts structured tasks
- Real-time streaming of agent reasoning via Server-Sent Events (SSE)
- Assignee recommendations based on team member skills and availability
- Configurable auto-apply threshold for high-confidence assignments
- Full provenance tracking: every AI decision is traceable back to a source span

### Human Review Queue
- Review, edit, approve, or reject AI-generated task candidates
- Batch approval/rejection
- Full revision history for each candidate
- Undo support for approval/rejection decisions

### Team Management
- People with roles, skills, and availability settings
- Workspace role-based access control (owner / admin / manager / member / viewer)
- Organization-level membership (owner / admin / member)

### Feedback & Analytics
- Tracks every human review decision as a feedback event
- Dashboard with AI accuracy metrics over time
- Useful for monitoring model performance and tuning thresholds

### Webhooks
- Subscribe to task lifecycle events
- Configurable per-workspace webhook endpoints
- Delivery log with retry status

### Internationalization
- Full English and Japanese UI support
- Browser language auto-detection with `localStorage` persistence

## Technology Stack at a Glance

| Layer | Technology |
|---|---|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS, shadcn/ui, TanStack Query |
| Backend | Python, FastAPI, SQLAlchemy 2.0, Pydantic |
| AI | Google Gemini (gemini-2.5-flash-lite) or OpenAI-compatible models |
| Database | PostgreSQL 16 |
| Migrations | Alembic |
| Container | Docker Compose |
| Non-Docker | PM2 process manager |

## Documentation Index

| Document | Description |
|---|---|
| [Architecture](./architecture.md) | System architecture, component diagram, and data model |
| [AI Pipeline](./ai-pipeline.md) | AI agent framework, extraction flow, and resilience patterns |
| [Database](./database.md) | Database schema and migration history |
| [API Reference](./api.md) | Backend REST API endpoints |
| [Frontend](./frontend.md) | Frontend structure, pages, and state management |
| [Configuration](./configuration.md) | Environment variables and configuration options |
| [Deployment](./deployment.md) | Docker and PM2 deployment instructions |
| [Testing](./testing.md) | Test suite structure and how to run tests |
