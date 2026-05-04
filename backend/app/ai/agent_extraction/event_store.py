from __future__ import annotations

import asyncio
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

_TTL_SECONDS = 3600


@dataclass
class AgentLoopEvent:
    id: str
    job_id: str
    event_type: str
    iteration: int | None = None
    tool_name: str | None = None
    display_message: str = ""
    message: str | None = None
    output: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def _display_message_for_event(
    *,
    event_type: str,
    iteration: int | None,
    tool_name: str | None,
    message: str | None,
) -> str:
    if event_type == "loop_started":
        return "Starting AI analysis..."

    if event_type == "iteration_started":
        round_no = iteration if iteration is not None else "?"
        return f"Thinking... (round {round_no})"

    if event_type == "thinking":
        return "Reasoning about the content..."

    if event_type == "reasoning":
        return "Planning next steps..."

    if event_type == "thinking_start":
        return "Reasoning about the content..."

    if event_type == "thinking_delta":
        return ""  # deltas have no display message — content is the message itself

    if event_type == "thinking_end":
        return ""

    if event_type == "text_start":
        return "Planning next steps..."

    if event_type == "text_delta":
        return ""

    if event_type == "text_end":
        return ""

    if event_type == "tool_call":
        tool_messages = {
            "get_assignee_skills": "Looking up team members and skills...",
            "create_tasks": "Creating tasks...",
            "recommend_assignees": "Recommending assignees...",
            "finalize_extraction": "Finalizing results...",
        }
        if tool_name in tool_messages:
            return tool_messages[tool_name]
        if tool_name:
            return f"Using tool: {tool_name}"
        return "Running analysis tool..."

    if event_type == "tool_result":
        if tool_name:
            return f"Got results from {tool_name}"
        return "Got tool results"

    if event_type == "finalized":
        return "Analysis complete!"

    return message or event_type.replace("_", " ").capitalize()


_events_by_job: dict[str, list[AgentLoopEvent]] = {}
_subscribers_by_job: dict[str, list["_Subscriber"]] = {}
_lock = threading.Lock()


@dataclass
class _Subscriber:
    queue: asyncio.Queue[dict[str, Any]]
    loop: asyncio.AbstractEventLoop


def _evict_stale_locked(now_ts: float) -> None:
    cutoff = now_ts - _TTL_SECONDS
    stale_job_ids = []
    for job_id, events in _events_by_job.items():
        if not events:
            stale_job_ids.append(job_id)
            continue
        _events_by_job[job_id] = [
            event for event in events if event.created_at.timestamp() >= cutoff
        ]
        if not _events_by_job[job_id]:
            stale_job_ids.append(job_id)
    for job_id in stale_job_ids:
        _events_by_job.pop(job_id, None)
        _subscribers_by_job.pop(job_id, None)


def subscribe(job_id: str) -> tuple[asyncio.Queue[dict[str, Any]], Callable[[], None]]:
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    subscriber = _Subscriber(queue=queue, loop=asyncio.get_running_loop())

    with _lock:
        _subscribers_by_job.setdefault(job_id, []).append(subscriber)

    def unsubscribe() -> None:
        with _lock:
            subscribers = _subscribers_by_job.get(job_id)
            if not subscribers:
                return
            try:
                subscribers.remove(subscriber)
            except ValueError:
                return
            if not subscribers:
                _subscribers_by_job.pop(job_id, None)

    return queue, unsubscribe


def append_event(
    *,
    job_id: str,
    event_type: str,
    iteration: int | None = None,
    tool_name: str | None = None,
    message: str | None = None,
    output: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AgentLoopEvent:
    display_message = _display_message_for_event(
        event_type=event_type,
        iteration=iteration,
        tool_name=tool_name,
        message=message,
    )
    event = AgentLoopEvent(
        id=str(uuid.uuid4()),
        job_id=job_id,
        event_type=event_type,
        iteration=iteration,
        tool_name=tool_name,
        display_message=display_message,
        message=message,
        output=output,
        metadata=metadata or {},
    )
    payload = asdict(event)
    now_ts = datetime.now(timezone.utc).timestamp()
    subscribers: list[_Subscriber] = []
    with _lock:
        _evict_stale_locked(now_ts)
        _events_by_job.setdefault(job_id, []).append(event)
        subscribers = list(_subscribers_by_job.get(job_id, []))

    stale_subscribers: list[_Subscriber] = []
    for subscriber in subscribers:
        try:
            subscriber.loop.call_soon_threadsafe(subscriber.queue.put_nowait, payload)
        except RuntimeError:
            stale_subscribers.append(subscriber)

    if stale_subscribers:
        with _lock:
            current = _subscribers_by_job.get(job_id)
            if current:
                _subscribers_by_job[job_id] = [
                    subscriber
                    for subscriber in current
                    if subscriber not in stale_subscribers
                ]
                if not _subscribers_by_job[job_id]:
                    _subscribers_by_job.pop(job_id, None)
    return event


def get_events(job_id: str) -> list[dict[str, Any]]:
    now_ts = datetime.now(timezone.utc).timestamp()
    with _lock:
        _evict_stale_locked(now_ts)
        events = list(_events_by_job.get(job_id, []))
    return [asdict(event) for event in events]
