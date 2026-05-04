from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

try:
    from starlette.middleware.sessions import SessionMiddleware
except ModuleNotFoundError:  # pragma: no cover - test environments may omit it
    SessionMiddleware = None

from app.config import get_settings
from app.routers import (
    ai,
    auth,
    feedback_analytics,
    health,
    people,
    task_activity,
    task_candidates,
    tasks,
    workspaces,
    projects,
    webhooks,
)

app = FastAPI(title="AI Task Management API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if SessionMiddleware is not None:
    app.add_middleware(
        SessionMiddleware,
        secret_key=get_settings().session_secret_key,
        session_cookie=get_settings().session_cookie_name,
        https_only=get_settings().session_cookie_secure,
        same_site="lax",
    )

app.include_router(tasks.router)
app.include_router(people.router)
app.include_router(ai.router)
app.include_router(auth.router)
app.include_router(workspaces.router)
app.include_router(task_candidates.router)
app.include_router(feedback_analytics.router)
app.include_router(task_activity.router)
app.include_router(projects.router)
app.include_router(webhooks.router)
app.include_router(health.router)
