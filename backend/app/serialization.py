"""Shared serialization helpers for JSON-safe value conversion."""

from datetime import date
from enum import Enum
from uuid import UUID


def to_json_value(value):
    """Convert model attribute values to JSON-serializable primitives.

    Handles enums, UUIDs, and dates.  Used by task and task-candidate
    routers when building activity/feedback event payloads.
    """
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    return value
