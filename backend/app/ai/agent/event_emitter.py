"""EventEmitter protocol — decouples the runner from any specific event store.

The existing ``agent_extraction.event_store`` implements this protocol
via a thin adapter.  Agents that don't need SSE streaming can ignore this
entirely (the runner treats emitters as optional).
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class EventEmitter(Protocol):
    """Anything that can receive structured agent loop events."""

    def emit(
        self,
        event_type: str,
        *,
        iteration: int | None = None,
        tool_name: str | None = None,
        message: str | None = None,
        output: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record one event.  Implementations must be thread-safe."""
        ...


class NullEmitter:
    """Default no-op emitter — silently discards all events."""

    def emit(
        self,
        event_type: str,
        *,
        iteration: int | None = None,
        tool_name: str | None = None,
        message: str | None = None,
        output: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        pass


class JobEventEmitter:
    """Adapter that bridges the ``EventEmitter`` protocol to the
    existing ``agent_extraction.event_store.append_event`` function.
    """

    def __init__(self, job_id: str) -> None:
        self.job_id = job_id

    def emit(
        self,
        event_type: str,
        *,
        iteration: int | None = None,
        tool_name: str | None = None,
        message: str | None = None,
        output: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        # Lazy import to avoid circular deps
        from app.ai.agent_extraction.event_store import append_event

        try:
            append_event(
                job_id=self.job_id,
                event_type=event_type,
                iteration=iteration,
                tool_name=tool_name,
                message=message,
                output=output,
                metadata=metadata,
            )
        except Exception:  # noqa: BLE001
            pass  # event emission should never crash the agent
