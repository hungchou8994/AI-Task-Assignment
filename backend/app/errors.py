"""Application error hierarchy — convenience wrappers around HTTPException.

Inspired by the Paperclip pattern: thin helpers that keep routers and services
focused on business logic instead of status-code boilerplate.

Usage in routers/services:
    from app.errors import NotFound, Conflict, BadRequest

    raise NotFound("Task")           # 404 "Task not found"
    raise Conflict("Email in use")   # 409
    raise BadRequest("Self-dependency not allowed")  # 400
"""

from __future__ import annotations

from fastapi import HTTPException


class NotFound(HTTPException):
    """404 — resource does not exist."""

    def __init__(self, resource: str = "Resource") -> None:
        super().__init__(status_code=404, detail=f"{resource} not found")


class Conflict(HTTPException):
    """409 — state conflict (duplicate, invalid transition, etc.)."""

    def __init__(self, detail: str = "Conflict") -> None:
        super().__init__(status_code=409, detail=detail)


class BadRequest(HTTPException):
    """400 — client sent invalid data."""

    def __init__(self, detail: str = "Bad request") -> None:
        super().__init__(status_code=400, detail=detail)


class Unauthorized(HTTPException):
    """401 — authentication required or failed."""

    def __init__(self, detail: str = "Authentication required") -> None:
        super().__init__(status_code=401, detail=detail)


class Forbidden(HTTPException):
    """403 — authenticated but not authorized."""

    def __init__(self, detail: str = "Forbidden") -> None:
        super().__init__(status_code=403, detail=detail)
